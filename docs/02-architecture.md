# Architecture

## Overview

A Home Assistant custom component (`custom_components/vitotrol/`) that communicates
directly with the Viessmann Vitotrol cloud SOAP API to expose boiler data and controls
as native HA entities. No MQTT broker required.

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
│  │  ┌──────────┬──────────┬───────┬┴───┬──────┐  │   │
│  │  │ Sensor   │ Binary   │Climate│Swit│Number│  │   │
│  │  │ Platform │ Sensor   │Entity │ ch │Entity│  │   │
│  │  └──────────┴──────────┴───────┴────┴──────┘  │   │
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
├── __init__.py              # Integration setup, platform forwarding
├── manifest.json            # Integration metadata for HA
├── const.py                 # Domain, attribute IDs, platform list
├── api.py                   # Async SOAP API client (port of go-vitotrol)
├── coordinator.py           # DataUpdateCoordinator for polling
├── config_flow.py           # UI-based configuration + options flow
├── entity.py                # Base entity class with shared device_info
├── sensor.py                # Temperature & counter sensors
├── binary_sensor.py         # Pump/burner/mode status sensors
├── climate.py               # Main heating climate entity
├── switch.py                # Party mode & energy saving switches
├── number.py                # Writable temperature setpoints
├── diagnostics.py           # Debug diagnostics dump
├── strings.json             # Config flow UI strings
└── translations/
    └── en.json              # English translations for all entities
```

## Component Layers

### Layer 1: API Client (`api.py`)

A pure async Python port of the `go-vitotrol` SOAP client. No HA dependencies.

**Class: `VitotrolAPI`**
- Manages SOAP communication via `aiohttp`
- Handles cookie-based session management (manual cookie dict, not shared HA jar)
- Provides typed methods for each SOAP operation
- Implements the async wait pattern for RefreshData/WriteData
- Raises `VitotrolError` / `VitotrolAuthError` on failures

**Class: `VitotrolDevice`** (dataclass)
- Holds device identity: location_id, location_name, device_id, device_name
- Holds status: has_error, is_connected

**Key methods**:
```
login() → None
get_devices() → list[VitotrolDevice]
refresh_data_wait(device, attr_ids) → None        # fire + poll until done
get_data(device, attr_ids) → dict[int, str]        # attr_id → raw value string
write_data_wait(device, attr_id, value) → None     # fire + poll until done
```

**Session strategy**: Use HA's shared `aiohttp.ClientSession` (via
`async_get_clientsession`), but manage cookies in a private dict passed
as a `Cookie` header. This avoids polluting HA's shared cookie jar while
benefiting from HA's connection pool.

### Layer 2: Coordinator (`coordinator.py`)

**Class: `VitotrolCoordinator(DataUpdateCoordinator)`**

Responsibilities:
- Polls all devices on a configurable interval (default 60s)
- For each device: RefreshData → wait → GetData
- Re-authenticates on API errors (login + retry once)
- Stores data as `dict[int, dict[int, str]]` → `{device_id: {attr_id: value}}`
- Handles attribute discovery: starts with all known attrs, tracks which ones
  the device actually supports

**Data flow per update cycle**:
```
1. For each device:
   a. RefreshData(device, supported_attr_ids)  — triggers device data upload
   b. Poll RequestRefreshStatus until done     — wait ~8-15s
   c. GetData(device, supported_attr_ids)      — read values from server
2. If any step fails:
   a. Re-login
   b. Retry once
   c. If still fails → raise UpdateFailed
```

**Attribute discovery** (first update only):
```
1. Try RefreshData + GetData with all known attribute IDs
2. If it fails, fall back to GetData only (reads cached/stale data)
3. Track which attr_ids actually returned values
4. On subsequent updates, only request attrs that worked before
```

### Layer 3: Config Flow (`config_flow.py`)

**User step**: Username (email) + password
- Validates by attempting Login + GetDevices
- Unique ID = username (prevents duplicate entries for same account)
- Stores credentials in config entry data

**Options flow**: Scan interval (30-600 seconds, default 60)
- Stored in config entry options
- Coordinator picks up changes via listener

### Layer 4: Integration Setup (`__init__.py`)

**`async_setup_entry`**:
1. Get shared aiohttp session
2. Create VitotrolAPI with credentials from config entry
3. Login + GetDevices
4. Create VitotrolCoordinator
5. Run first refresh (`async_config_entry_first_refresh`)
6. Store API + coordinator + devices in `hass.data[DOMAIN][entry_id]`
7. Forward to all platforms

**`async_unload_entry`**:
1. Unload platforms
2. Remove from `hass.data`

### Layer 5: Entity Platforms

All entities extend `VitotrolEntity(CoordinatorEntity)` which provides:
- `device_info` → Viessmann device in device registry
- `unique_id` → `{device_id}_{entity_key}`
- `available` → checks if attr_id exists in coordinator data
- `_attr_has_entity_name = True` → names come from translations
- Value reading from `coordinator.data[device_id][attr_id]`

## Entity Mapping

### Sensors (`sensor.py`)

| Entity Key | Attr ID | Device Class | State Class | Unit |
|---|---|---|---|---|
| indoor_temperature | 5367 | TEMPERATURE | MEASUREMENT | °C |
| outdoor_temperature | 5373 | TEMPERATURE | MEASUREMENT | °C |
| boiler_temperature | 5374 | TEMPERATURE | MEASUREMENT | °C |
| hot_water_temperature | 5381 | TEMPERATURE | MEASUREMENT | °C |
| hot_water_outlet_temperature | 5382 | TEMPERATURE | MEASUREMENT | °C |
| heating_water_outlet_temperature | 6052 | TEMPERATURE | MEASUREMENT | °C |
| smoke_temperature | 5372 | TEMPERATURE | MEASUREMENT | °C |
| burner_hours | 104 | DURATION | TOTAL_INCREASING | h |
| burner_starts | 111 | — | TOTAL_INCREASING | — |
| operating_mode | 708 | ENUM | — | — |
| valve_3way_status | 5389 | ENUM | — | — |
| current_error | 7184 | — (diagnostic) | — | — |

### Binary Sensors (`binary_sensor.py`)

| Entity Key | Attr ID | Device Class | On values |
|---|---|---|---|
| burner | 600 | RUNNING | "1" |
| internal_pump | 245 | RUNNING | "1", "3" |
| heating_pump | 729 | RUNNING | "1" |
| circulation_pump | 7181 | RUNNING | "1" |
| frost_protection | 717 | SAFETY | "1" |
| holiday_mode | 714 | — | "1" |

### Climate (`climate.py`)

One climate entity per device. The main heating control.

| Property | Source |
|---|---|
| `current_temperature` | IndoorTemp (5367) |
| `target_temperature` | HeatNormalTemp (82) |
| `hvac_mode` | OperatingModeRequested (92) |
| `hvac_action` | BurnerState (600) + OperatingModeCurrent (708) |
| `preset_mode` | EnergySavingMode (7852) + PartyMode (7855) |

**HVAC mode mapping** (follows ViCare pattern):

| HA HVAC Mode | Vitotrol OperatingModeRequested value |
|---|---|
| OFF | 0 (standby) |
| AUTO | 2 (heating + DHW, schedule-based) |
| HEAT | 4 (continuous normal) |

**HVAC action mapping**:

| HA HVAC Action | Condition |
|---|---|
| OFF | OperatingModeCurrent == 0 (stand-by) |
| HEATING | BurnerState == "1" |
| IDLE | BurnerState == "0" and system not in stand-by |

**Preset mapping**:

| HA Preset | Action |
|---|---|
| NONE | EnergySavingMode=0, PartyMode=0 |
| ECO | EnergySavingMode=1 |
| BOOST | PartyMode=1 |

**Write operations**:
- `set_temperature` → WriteData HeatNormalTemp
- `set_hvac_mode` → WriteData OperatingModeRequested
- `set_preset_mode` → WriteData EnergySavingMode / PartyMode

### Switches (`switch.py`)

| Entity Key | Attr ID | Category |
|---|---|---|
| party_mode | 7855 | CONFIG |
| energy_saving_mode | 7852 | CONFIG |

Write "1" to enable, "0" to disable.

### Numbers (`number.py`)

| Entity Key | Attr ID | Min | Max | Step | Category |
|---|---|---|---|---|---|
| hot_water_setpoint | 51 | 10 | 60 | 1.0 | CONFIG |
| reduced_temperature_setpoint | 85 | 3 | 30 | 0.5 | CONFIG |
| party_mode_temperature | 79 | 10 | 30 | 0.5 | CONFIG |

## Data Flow

### Polling (every 60s)

```
Coordinator._async_update_data()
  │
  ├─► api.refresh_data_wait(device, attr_ids)
  │     ├─► SOAP RefreshData         → refresh_id
  │     ├─► sleep(8s)
  │     ├─► SOAP RequestRefreshStatus → status
  │     ├─► (repeat until status != 0 or timeout)
  │     └─► return
  │
  ├─► api.get_data(device, attr_ids)
  │     ├─► SOAP GetData             → {attr_id: value}
  │     └─► return data dict
  │
  └─► return {device_id: {attr_id: value}}
        │
        ▼
      CoordinatorEntity.async_write_ha_state() (automatic)
        │
        ▼
      Each entity reads its value from coordinator.data
```

### Writing a Value (e.g., set_temperature)

```
ClimateEntity.async_set_temperature(temperature=22.0)
  │
  ├─► api.write_data_wait(device, ATTR_HEAT_NORMAL_TEMP, "22.0")
  │     ├─► SOAP WriteData           → refresh_id
  │     ├─► sleep(4s)
  │     ├─► SOAP RequestWriteStatus  → status
  │     └─► (repeat until done or timeout)
  │
  ├─► Optimistic state update: self._attr_target_temperature = 22.0
  │
  └─► self.async_write_ha_state()    → immediate UI update
        │
        ▼
      Next coordinator poll confirms the value from the device
```

### Error Recovery

```
Any API call fails
  │
  ├─► Re-login (api.login())
  ├─► Retry the operation once
  │
  ├─► Success → continue normally
  └─► Failure → raise UpdateFailed
                  │
                  ▼
                HA marks all entities as unavailable
                Coordinator retries on next interval
```

## Device Registry

Each physical Viessmann device appears as one device in HA:

```python
DeviceInfo(
    identifiers={(DOMAIN, str(device.device_id))},
    name=device.device_name,         # e.g. "VT 200 (HO1C)"
    manufacturer="Viessmann",
    model="Vitotrol",
    configuration_url="https://vitotrolapp.viessmann-climatesolutions.com",
)
```

All entities for that device are grouped under it in the HA UI.

## Configuration Storage

**Config entry data** (set during config flow, not changed):
```python
{
    "username": "user@example.com",
    "password": "secret",
}
```

**Config entry options** (changeable via options flow):
```python
{
    "scan_interval": 60,  # seconds
}
```
