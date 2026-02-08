# Attribute Configurability Design

## The Problem

Not all Viessmann devices support the same attributes. The Vitotrol SOAP API
will error on the entire request if you include an unsupported attribute.
We need to know exactly which attributes a device supports before polling.

## Solution: GetTypeInfo + Enable-All Pattern

### Discovery: `GetTypeInfo` API Call

The SOAP API has a `GetTypeInfo` operation (see `01-findings.md`) that returns
**all available datapoints** for a device in a single, fast (~1s) call.
No binary search, no brute-force scanning.

`GetTypeInfo(AnlageId, GeraetId)` returns every attribute the device supports,
with full metadata: name, type, unit, min/max, read/write flags, enum values,
group, heating circuit, and factory default.

The go-vitotrol library implements this in `device.go:GetTypeInfo()`.

### UX: Standard HA Enable/Disable Pattern

Follow the pattern used by most well-built HA integrations:

1. **Call GetTypeInfo** during setup → get the full device attribute catalog
2. **Create entities for ALL attributes** the device reports
3. **Known attributes** (our hardcoded entity definitions) → `entity_registry_enabled_default = True`
4. **All other attributes** → `entity_registry_enabled_default = False`
5. **User enables what they want** via standard HA UI ("X disabled entities" on device page)

This means:
- **No custom selection UI** — standard HA entity enable/disable
- **No textarea for custom attributes** — everything comes from GetTypeInfo
- **No binary search discovery** — single API call
- **No options flow for attribute management** — options flow only has scan interval
- **Zero custom UX to build or maintain**

### What the User Sees

On the device page in HA:

```
Viessmann VT 200 (HO1C)
────────────────────────
  Indoor Temperature          21.5 °C
  Outdoor Temperature          8.2 °C
  Boiler Temperature          45.3 °C
  Hot Water Temperature       52.1 °C
  Burner Status               On
  Operating Mode              Heat + DHW
  ...

  24 disabled entities          ← click to browse and enable
```

Clicking "24 disabled entities" shows the full list. The user finds an
attribute they want (e.g. "Elektrische Leistung"), clicks it, toggles
"Enabled" to on. Standard HA behavior, nothing custom.

## Entity Type Selection

### Known Attributes (enabled by default)

These have hand-crafted entity definitions in our platform files with proper
device classes, icons, state classes, and translations:

| Platform | Attributes |
|---|---|
| `sensor` | Temperatures (indoor, outdoor, boiler, hot water, smoke, etc.), burner hours, burner starts, operating mode, 3-way valve, current error |
| `binary_sensor` | Burner state, pump statuses, frost protection, holiday mode |
| `climate` | Main heating control (HVAC mode + preset) |
| `switch` | Party mode, energy saving mode |
| `number` | Temperature setpoints (hot water, reduced, party mode) |

### Additional Attributes (disabled by default)

Created dynamically from GetTypeInfo metadata. Entity type is inferred:

| GetTypeInfo metadata | Entity type | Example |
|---|---|---|
| DOUBLE + read-only | `sensor` | Electrical power (kW) |
| DOUBLE + writable + min/max | `number` | Unknown setpoint |
| ENUM + read-only | `sensor` | Status enum |
| ENUM + writable | `select` | Mode selector with option labels |
| Boolean-like (0/1) + read-only | `binary_sensor` | On/off status |
| Boolean-like (0/1) + writable | `switch` | On/off toggle |

Entity metadata from the API:
- **Name**: from `DatenpunktName` (German, user can rename in HA UI)
- **Unit**: from `EinheitBezeichnung` (°C, kW, h, ...)
- **Device class**: inferred from unit where possible (°C → temperature, kW → power)
- **Min/max**: from `MinimalWert`/`MaximalWert` (for number entities)
- **Options**: from enum values (for select entities)
- **Unique ID**: `{device_id}_attr_{attr_id}`

## Polling Strategy

Only **enabled** entities get polled. The coordinator builds the attribute ID
list from entities that are currently enabled in the entity registry:

```
GetTypeInfo (once at setup)
    → creates entities for ALL attributes
    → user enables/disables via HA UI
    → coordinator polls only enabled attribute IDs
    → RefreshData + GetData with the enabled set
```

This keeps API requests minimal — we never request attributes the user
doesn't care about.

## Implementation

### api.py

Add `get_type_info()` method:

```python
async def get_type_info(
    self, location_id: int, device_id: int
) -> list[dict]:
    """Get all available datapoint definitions for a device."""
```

SOAP request: just `AnlageId` + `GeraetId`, no attribute list needed.
Response parsing: handle enum pattern where base entries have plain IDs
(`"92"`) and enum value entries have `"ID-N"` format (`"92-0"`) with the
label in `MinimalWert`.

### coordinator.py

- Call `get_type_info()` once during setup, cache the result
- Remove binary search discovery entirely
- Build poll list from enabled entities only
- Store the attribute catalog for entity platforms to use

### Entity platforms

Each platform's `async_setup_entry`:
1. Create entities for known attributes (from hardcoded descriptions)
   that exist in the GetTypeInfo catalog → `entity_registry_enabled_default = True`
2. Create entities for additional attributes from the catalog,
   using inferred entity types → `entity_registry_enabled_default = False`

### config_flow.py

Options flow simplifies to just scan interval. No attribute management needed.

### What gets removed

- Binary search discovery logic in coordinator
- Custom attributes textarea in options flow
- `VitotrolCustomSensor` class
- `custom_attributes` in config entry options
- `_apply_custom_attrs()` in `__init__.py`
- `CONF_CUSTOM_ATTRIBUTES` constant

## Migration

Users coming from the current implementation (textarea custom attrs) will
find their custom attributes already present as disabled entities after the
migration. They just need to enable them in the HA UI. The textarea data
can be ignored/cleaned up.

## Phases

| Phase | What |
|---|---|
| **1** | Add `get_type_info()` to api.py |
| **2** | Replace binary search with GetTypeInfo in coordinator |
| **3** | Create entities for all attributes with proper enable defaults |
| **4** | Smart entity type inference from metadata |
| **5** | Remove old custom attribute machinery |
