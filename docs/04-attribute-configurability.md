# Attribute Configurability Design

## The Problem

Not all Viessmann devices support the same attributes. Additionally, there are
hundreds of undocumented attributes beyond the ~28 "known" ones. Real users already
use custom attributes via the `NAME-0xNNNN` pattern:

```yaml
# Real-world example from vitotrol2mqtt config
fields:
  - IndoorTemp                              # known attribute
  - OutdoorTemp                             # known attribute
  - info_elektrische_leistung_fcu_r-0x2637  # custom: electrical power (FCU)
  - info_thermische_leistung_fcu_r-0x266c   # custom: thermal power (FCU)
  - info_energie_gesamt_r-0x2e68            # custom: total energy
  - info_waermemenge_fcu_r-0x2639           # custom: heat quantity (FCU)
```

Requesting an unsupported attribute causes the Vitotrol API to error for the
entire request — so we can't just blindly request everything.

## Three categories of attributes

| Category | Example | Count | How to handle |
|---|---|---|---|
| **Known & common** | IndoorTemp, OutdoorTemp, BoilerTemp | ~20 | Auto-discover on first setup |
| **Known & rare** | CirculationPumpState, HolidaysStatus | ~8 | Auto-discover on first setup |
| **Custom / undocumented** | `info_energie_gesamt_r-0x2e68` | Hundreds | User adds manually |

## Design: Three-tier approach

### Tier 1: Auto-discovery of known attributes (MVP)

On first coordinator refresh, probe all known attributes to find which ones
the device supports.

**Strategy**: Binary search discovery

```
1. Try RefreshData + GetData with ALL known attribute IDs
2. If it succeeds → all attributes supported, done
3. If it fails → split the list in half, try each half
4. Recurse until we find the exact set of supported attributes
5. Cache the supported set in config entry data (persists across restarts)
```

This runs once during initial setup (or when the user triggers re-discovery).
Worst case with ~28 attributes: ~10 API calls × ~10s each = ~2 minutes.
Acceptable as a one-time setup cost.

**Stored as**:
```python
# In config entry data (persistent)
entry.data["supported_attrs"] = [5367, 5373, 5374, ...]  # list of working attr IDs
```

Entities are only created for attributes that passed discovery.

### Tier 2: Custom attributes via Options Flow (post-MVP)

Users can add custom attributes through the HA options flow UI.

**Options flow step "custom_attributes"**:

```
┌─────────────────────────────────────────┐
│  Custom Attributes                      │
│                                         │
│  Add custom attribute IDs to poll from  │
│  your Viessmann device. Use the format  │
│  name-0xHHHH (e.g. my_sensor-0x2637).  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │ info_elektrische_leistung-0x2637  │  │
│  │ info_thermische_leistung-0x266c   │  │
│  │ info_energie_gesamt-0x2e68        │  │
│  │ info_waermemenge_fcu-0x2639       │  │
│  │                                   │  │
│  └───────────────────────────────────┘  │
│  (one per line)                         │
│                                         │
│              [Submit]                   │
└─────────────────────────────────────────┘
```

**On submit**:
1. Parse each line: extract name and hex ID
2. Validate the hex ID format
3. Test each new attribute: try GetData for the attr ID
4. If valid: add to config entry options, create sensor entity
5. If invalid: show error for the specific failing attribute

**Stored as**:
```python
# In config entry options (persistent, user-editable)
entry.options["custom_attributes"] = [
    {"name": "info_elektrische_leistung", "attr_id": 9783},  # 0x2637
    {"name": "info_thermische_leistung", "attr_id": 9836},   # 0x266c
    {"name": "info_energie_gesamt", "attr_id": 11880},        # 0x2e68
    {"name": "info_waermemenge_fcu", "attr_id": 9785},        # 0x2639
]
```

**Entity creation for custom attributes**:
- Always created as `sensor` entities
- Device class: none (user can customize via HA UI entity settings)
- State class: `SensorStateClass.MEASUREMENT` (safe default)
- Unit: none (user can set via HA entity customization)
- Name: derived from the user-provided name part (underscores → spaces, title case)
  e.g. `info_elektrische_leistung` → "Info Elektrische Leistung"
- Translation key: not used (dynamic name from user input)
- Unique ID: `{device_id}_custom_{attr_id_hex}`
- Entity ID: `sensor.vitotrol_{device_name}_{name}`

### Tier 3: Attribute Scanner (future enhancement)

A HA service or button entity that probes ranges of attribute IDs to discover
what the device supports.

**Service: `vitotrol.scan_attributes`**:
```yaml
# Service call
service: vitotrol.scan_attributes
data:
  device_id: "12345"
  start_id: "0x2600"   # hex
  end_id: "0x2700"     # hex
```

**Behavior**:
1. Iterate through the ID range
2. For each ID, try GetData (no RefreshData needed — just check if server has cached data)
3. Return list of IDs that returned a value
4. Fire a persistent notification or event with results

**Output**:
```
Scan complete for device VT 200 (HO1C).
Found 4 responding attributes in range 0x2600-0x2700:
  0x2637 = 1.23
  0x2639 = 456.7
  0x266c = 2.34
  0x2690 = 0.0
```

This helps users discover attributes without trial and error.
Could also be exposed as a button entity "Scan for attributes" that triggers
the scan and logs results.

## Implementation in the coordinator

The coordinator needs to manage two sets of attributes:

```python
class VitotrolCoordinator:
    def __init__(self, ...):
        # Known attributes that passed auto-discovery
        self._known_attr_ids: list[int] = []

        # Custom attributes from options flow
        self._custom_attr_ids: list[int] = []

    @property
    def all_attr_ids(self) -> list[int]:
        return self._known_attr_ids + self._custom_attr_ids
```

Both sets are polled together in a single RefreshData + GetData cycle.
The data dict makes no distinction between known and custom — all values
are stored the same way:

```python
coordinator.data = {
    device_id: {
        5367: "21.5",     # known: IndoorTemp
        9783: "1.23",     # custom: info_elektrische_leistung
        ...
    }
}
```

## Implementation in entity platforms

**Known attributes** → entity descriptions defined in code (sensor.py, etc.)
**Custom attributes** → dynamically created sensors in sensor.py's `async_setup_entry`:

```python
async def async_setup_entry(hass, entry, async_add_entities):
    # 1. Create entities for known attributes (from SENSOR_DESCRIPTIONS)
    entities = [...]

    # 2. Create entities for custom attributes (from options)
    for custom in entry.options.get("custom_attributes", []):
        if custom["attr_id"] in coordinator.data.get(device_id, {}):
            entities.append(VitotrolCustomSensor(coordinator, device, custom))

    async_add_entities(entities)
```

## Options flow: also allow toggling known attributes

For power users, the options flow could also allow enabling/disabling
specific known attributes. This covers the case where auto-discovery
includes an attribute the user doesn't want, or misses one they do want.

```
┌─────────────────────────────────────────┐
│  Monitored Attributes                   │
│                                         │
│  ☑ Indoor temperature                  │
│  ☑ Outdoor temperature                 │
│  ☑ Boiler temperature                  │
│  ☐ Hot water outlet temperature        │
│  ☑ Smoke temperature                   │
│  ...                                    │
│                                         │
│  Scan interval: [60] seconds            │
│                                         │
│              [Submit]                   │
└─────────────────────────────────────────┘
```

However, this adds UI complexity. For MVP, auto-discovery with no toggle
is sufficient. Users can disable individual entities in the HA entity
settings.

## Migration path from vitotrol2mqtt

Users coming from vitotrol2mqtt have a YAML config with their working
field list. The options flow text area for custom attributes accepts the
same `name-0xNNNN` format, making migration straightforward:

```
# Copy from vitotrol2mqtt.yml fields list, paste custom ones into options:
info_elektrische_leistung_fcu_r-0x2637
info_thermische_leistung_fcu_r-0x266c
info_energie_gesamt_r-0x2e68
info_waermemenge_fcu_r-0x2639
```

Known attributes (IndoorTemp, OutdoorTemp, etc.) are handled automatically
and don't need to be entered.

## Phases

| Phase | What | When |
|---|---|---|
| MVP | Auto-discovery of known attributes | Phase 1 |
| MVP | Custom attributes via options flow | Phase 2 (can follow shortly) |
| Future | Attribute scanner service | After v1 release |
| Future | Toggleable known attributes in options | After v1 release |

## Impact on architecture docs

This design adds:
- **coordinator.py**: attribute discovery logic, dual attr ID lists
- **config_flow.py**: options flow step for custom attributes
- **sensor.py**: `VitotrolCustomSensor` class for dynamic custom entities
- **const.py**: no change (known attributes stay as constants)
- **api.py**: no change (already works with arbitrary attr IDs)
