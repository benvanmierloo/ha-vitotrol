# Architecture

## Overview

```
┌─────────────────────────────────────────────────────┐
│                  Home Assistant                      │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │         custom_components/vitotrol/           │   │
│  │                                               │   │
│  │  ┌─────────────┐    ┌─────────────────────┐  │   │
│  │  │ Config Flow  │    │   Coordinator       │  │   │
│  │  │ (setup UI)   │    │ (DataUpdateCoord.)  │  │   │
│  │  └──────┬───────┘    └──────────┬──────────┘  │   │
│  │         │                       │              │   │
│  │         │            ┌──────────┴──────────┐  │   │
│  │         └───────────►│    VitotrolAPI       │  │   │
│  │                      │  (SOAP client)      │  │   │
│  │                      └──────────┬──────────┘  │   │
│  │                                 │              │   │
│  │  ┌────────┬────────┬───────┬────┴┬──────┐    │   │
│  │  │ Sensor │ Binary │Climate│Swit-│Number│    │   │
│  │  │        │ Sensor │       │ ch  │      │    │   │
│  │  └────────┴────────┴───────┴─────┴──────┘    │   │
│  └───────────────────────────────────────────────┘   │
│                                                     │
└──────────────────────────┬──────────────────────────┘
                           │ HTTPS/SOAP
                           ▼
              ┌────────────────────────┐
              │  Viessmann Vitotrol    │
              │  Cloud API (SOAP)     │
              └────────────┬──────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  Viessmann Boiler      │
              │  (physical device)     │
              └────────────────────────┘
```

## File Structure

```
custom_components/vitotrol/
├── __init__.py          # Integration setup, platform forwarding
├── manifest.json        # Integration metadata for HA
├── const.py             # Domain, platform list, defaults
├── attributes.py        # Attribute registry (IDs, known attrs, entity type inference)
├── api.py               # Async SOAP API client (no HA dependencies)
├── coordinator.py       # DataUpdateCoordinator for polling
├── config_flow.py       # UI config flow + options flow
├── entity.py            # Base VitotrolEntity(CoordinatorEntity)
├── sensor.py            # Temperature & counter sensors
├── binary_sensor.py     # Pump/burner/mode binary sensors
├── climate.py           # Main heating climate entity
├── switch.py            # Party mode & energy saving switches
├── number.py            # Writable temperature setpoints
├── select.py            # Writable enum selectors
├── diagnostics.py       # Debug diagnostics dump
├── strings.json         # Config flow UI strings
└── translations/
    └── en.json          # English translations for all entities
```

## Layers

The code has five layers, each depending only on the layer below.

### Layer 1: API Client (`api.py`)

Pure async Python SOAP client with no Home Assistant dependencies.

- **`VitotrolAPI`** — Manages SOAP communication via `aiohttp`. Handles cookie-based sessions using a private dict (not HA's shared cookie jar). Provides typed methods for each SOAP operation and implements the async wait pattern for RefreshData/WriteData. Raises `VitotrolError` / `VitotrolAuthError` on failures.
- **`VitotrolDevice`** — Dataclass holding device identity (location_id, device_id, names) and status flags (has_error, is_connected).

### Layer 2: Coordinator (`coordinator.py`)

**`VitotrolCoordinator(DataUpdateCoordinator)`** — Polls devices on a configurable interval (default 300s).

Key responsibilities:
- **Attribute discovery:** Calls `GetTypeInfo` once at setup to get the full device attribute catalog. Caches it for entity platforms.
- **Polling:** For each device: `RefreshData` → wait → `GetData`. Only polls attribute IDs that have enabled entities.
- **Error recovery:** Re-authenticates on API errors (login + retry once). If still failing, raises `UpdateFailed` so HA marks entities unavailable.

Data structure: `dict[int, dict[int, str]]` — `{device_id: {attr_id: raw_value_string}}`.

### Layer 3: Config Flow (`config_flow.py`)

- **User step:** Username + password. Validates by calling Login + GetDevices.
- **Options flow:** Scan interval (60-900s, default 300s).

### Layer 4: Integration Setup (`__init__.py`)

Wires API → coordinator → platform forwarding. Creates the API client, logs in, discovers devices, starts the coordinator, and forwards to entity platforms.

### Layer 5: Entity Platforms

All entities extend `VitotrolEntity(CoordinatorEntity)` (defined in `entity.py`), which provides shared device_info, unique_id generation, and value reading from coordinator data.

**Entity types:**

| Platform | Description | Examples |
|---|---|---|
| `sensor` | Read-only numeric and enum values | Temperatures, burner hours, operating mode |
| `binary_sensor` | Read-only on/off states | Burner, pumps, frost protection |
| `climate` | Main heating control | HVAC modes, presets, target temperature |
| `switch` | Writable on/off toggles | Party mode, energy saving mode |
| `number` | Writable numeric setpoints | Hot water temp, reduced temp |
| `select` | Writable enum selectors | Discovered via GetTypeInfo |

Write operations use **optimistic state updates** — the entity updates its state immediately after sending the write command, without waiting for the next poll to confirm.

## Attribute System

### Registry (`attributes.py`)

The attribute registry is a single table (`_TABLE`) that drives all entity creation. Each row is `(id, name, enabled, category)` — the category determines platform, unit, device class, and state class. Enum maps and binary sensor on-value overrides are in separate dicts keyed by attribute ID.

See [contributing.md](contributing.md#the-attribute-registry-attributespy) for the full format and how to add new attributes.

### Discovery and Entity Creation

1. **At setup**, the coordinator calls `GetTypeInfo` — a single fast API call that returns every datapoint the device supports, with metadata (name, type, unit, min/max, read/write flags, enum values).
2. **Known attributes** (in the registry) get entities with curated device classes, icons, and translations. Enabled by default.
3. **Additional attributes** get entities with metadata inferred from the API response (unit → device class, writable + min/max → number, writable enum → select, etc.). Disabled by default.
4. **Users enable what they want** via the standard HA UI ("X disabled entities" on the device page).
5. **Only enabled entities get polled** — the coordinator builds the attribute ID list from the entity registry.

### Climate Entity Mapping

The climate entity combines multiple attributes into a single HA control:

| Property | Source Attribute |
|---|---|
| `current_temperature` | Indoor temperature (5367) |
| `target_temperature` | Normal temp setpoint (82) |
| `hvac_mode` | Requested operating mode (92) |
| `hvac_action` | Burner state (600) + current mode (708) |
| `preset_mode` | Energy saving (7852) + party mode (7855) |

**HVAC mode mapping:**

| HA Mode | Vitotrol Mode |
|---|---|
| Off | 0 (standby) |
| Auto | 2 (heating + DHW, schedule-based) |
| Heat | 4 (continuous normal) |

**Presets:** ECO = energy saving mode, Boost = party mode. Mutually exclusive.

## Data Flow

### Polling Cycle

```
Coordinator._async_update_data()
  ├── api.refresh_data_wait(device, attr_ids)
  │     ├── SOAP RefreshData         → refresh_id
  │     ├── sleep(8s)
  │     ├── SOAP RequestRefreshStatus → status
  │     └── repeat until done or timeout
  ├── api.get_data(device, attr_ids)
  │     └── SOAP GetData             → {attr_id: value}
  └── return {device_id: {attr_id: value}}
        └── CoordinatorEntity.async_write_ha_state() (automatic)
```

### Write Flow (e.g. set_temperature)

```
ClimateEntity.async_set_temperature(temperature=22.0)
  ├── api.write_data_wait(device, attr_id, "22.0")
  │     ├── SOAP WriteData           → refresh_id
  │     ├── sleep(4s)
  │     └── poll RequestWriteStatus until done
  ├── Optimistic update: self._attr_target_temperature = 22.0
  └── self.async_write_ha_state()    → immediate UI update
```

### Error Recovery

```
API call fails
  ├── Re-login (api.login())
  ├── Retry the operation once
  ├── Success → continue normally
  └── Failure → raise UpdateFailed → HA marks entities unavailable
```
