# Contributing

## Development Setup

1. Clone the repository into your Home Assistant `custom_components` directory (or symlink it):
   ```
   cd /path/to/ha-config/custom_components
   git clone https://github.com/benvanmierloo/ha-vitotrol.git vitotrol
   ```

2. Restart Home Assistant to pick up the integration.

3. The integration has no external Python dependencies beyond what Home Assistant provides (`aiohttp`, `xml.etree.ElementTree`).

## Project Layout

See [architecture.md](architecture.md) for a full description of the layer structure and data flow.

```
custom_components/vitotrol/
├── api.py               # SOAP client (no HA deps, testable in isolation)
├── attributes.py        # Attribute registry table
├── coordinator.py       # DataUpdateCoordinator
├── entity.py            # Base entity class
├── config_flow.py       # Config + options flow
├── __init__.py          # Integration wiring
├── sensor.py            # Sensor entities
├── binary_sensor.py     # Binary sensor entities
├── climate.py           # Climate entity
├── switch.py            # Switch entities
├── number.py            # Number entities
├── select.py            # Select entities
└── diagnostics.py       # Diagnostics export
```

Dependencies flow downward: `const.py` → `api.py` → `coordinator.py` → `entity.py` → platform files.

## Adding a Known Attribute

Every Viessmann device exposes different attributes. Attributes not in our registry are still discovered via `GetTypeInfo` and created as disabled entities with inferred metadata — but adding them to the registry gives them proper English names, correct device classes, and enabled-by-default status.

If your device has attributes that aren't in the list, adding them is the easiest way to contribute.

### The attribute registry (`attributes.py`)

Everything is driven by a single table `_TABLE` and two optional override dicts. You don't need to touch any platform files.

**`_TABLE`** — one row per attribute:

```python
#   (id,    name,                          enabled, category)
    (5367,  "Indoor temperature",          True,    "temp"),
```

| Field | Description |
|---|---|
| `id` | The Vitotrol attribute ID (DatenpunktId). Find it in the `GetTypeInfo` response or in the diagnostics dump. |
| `name` | English display name shown in Home Assistant. |
| `enabled` | `True` = entity is enabled by default, `False` = created but disabled (user can enable in HA UI). Use `True` for common attributes, `False` for niche ones. |
| `category` | Determines the entity platform, unit, device class, and state class. See available categories below. |

**Available categories:**

| Category | Platform | Unit | Device class | Use for |
|---|---|---|---|---|
| `temp` | sensor | °C | temperature | Temperature readings |
| `power` | sensor | W | power | Power measurements |
| `energy` | sensor | kWh | energy | Cumulative energy (total_increasing) |
| `energy_h` | sensor | kWh | energy | Energy snapshots (measurement) |
| `pct` | sensor | % | — | Percentage values |
| `duration` | sensor | h | duration | Runtime hours (total_increasing) |
| `counter` | sensor | — | — | Counters like burner starts |
| `gas` | sensor | m³ | gas | Gas consumption |
| `weight` | sensor | kg | weight | Weight (total_increasing) |
| `weight_h` | sensor | kg | weight | Weight snapshots (measurement) |
| `enum` | sensor | — | enum | Read-only enum status (needs `_ENUM_MAPS` entry) |
| `text` | sensor | — | — | Plain text values |
| `diag` | sensor | — | — | Diagnostic info (shown under diagnostics category) |
| `running` | binary_sensor | — | running | On/off for pumps, burners |
| `safety` | binary_sensor | — | safety | Safety flags like frost protection |
| `bool` | binary_sensor | — | — | Generic on/off |
| `num_temp` | number | °C | temperature | Writable temperature setpoints |
| `num` | number | — | — | Other writable numeric values |
| `switch` | switch | — | — | Writable on/off toggles |
| `select` | select | — | — | Writable enum (needs `_ENUM_MAPS` entry) |
| `none` | — | — | — | No standalone entity (used by climate or not yet supported) |

### Examples

**Simple temperature sensor** — just add a row:
```python
(1234,  "Flow temperature",  True,  "temp"),
```

**Enum sensor** — add a row + an enum map:
```python
# In _TABLE:
(5678,  "Pump mode",  False,  "enum"),

# In _ENUM_MAPS:
5678: {"0": "Off", "1": "Normal", "2": "High"},
```

**Binary sensor with non-standard on-values** — add a row + on_values override:
```python
# In _TABLE:
(9999,  "Solar pump",  False,  "running"),

# In _ON_VALUES:
9999: ("1", "3"),  # values 1 and 3 both mean "on"
```

**Writable select** — add a row + an enum map:
```python
# In _TABLE:
(4321,  "DHW mode",  False,  "select"),

# In _ENUM_MAPS:
4321: {"0": "Off", "1": "Normal", "2": "Comfort"},
```

### Finding attribute IDs for your device

**Discovery script** (recommended for contributors) — a standalone script that logs into the Vitotrol API and dumps every attribute your device supports, with names, types, units, min/max, and read/write flags:

```
pip install -r scripts/requirements.txt
python scripts/discover.py --user YOUR_EMAIL --password YOUR_PASSWORD
```

Add `--values` to also fetch current cached values. You can also use environment variables:

```
VITOTROL_USER=... VITOTROL_PASSWORD=... python scripts/discover.py --values
```

The output is a table of all attributes — use it to identify which IDs to add to `_TABLE`.

**Other ways to find attribute IDs:**

1. **Diagnostics dump:** Go to the integration page in HA, click "Download diagnostics". The JSON file includes the full `GetTypeInfo` response with all attribute IDs, names, types, and value ranges for your device.

2. **HA logs:** Enable debug logging for `custom_components.vitotrol` — the coordinator logs the discovered attribute catalog at startup.

3. **Disabled entities:** Check the device page in HA — click "X disabled entities" to see all discovered attributes. The entity ID contains the attribute number.

### No platform file changes needed

The platform files (`sensor.py`, `binary_sensor.py`, `number.py`, `switch.py`, `select.py`) read from `ATTRIBUTE_REGISTRY` automatically. Adding a row to `_TABLE` (and optionally `_ENUM_MAPS` / `_ON_VALUES`) is all that's required.

## Adding a New Entity Platform

1. Create the platform file (e.g. `water_heater.py`).
2. Add the platform to `PLATFORMS` in `const.py`.
3. Implement `async_setup_entry` to create entities from coordinator data.
4. Extend `VitotrolEntity` from `entity.py` for shared device info and coordinator integration.
5. Add translations in `translations/en.json`.

## SOAP API Notes

See [api-reference.md](api-reference.md) for the full API documentation.

Key things to keep in mind when working with `api.py`:

- **Field names are mixed German/English.** The WSDL is the source of truth. Notable gotchas: the password field is `Passwort`, the write attribute field is `DatapointId` (not `DatenpunktId`).
- **Element order matters.** SOAP body elements should follow WSDL order (`AnlageId` before `GeraetId`).
- **HTTP 500 usually means malformed XML**, not a server error.
- **No `UseCache` element** exists in the WSDL schema for `GetData`.
- **GetData response items** are in `WerteListe`, not `DatenpunktValueV2`.

## Conventions

- All entity write operations should use **optimistic state updates** — update the entity's state attribute immediately after the write, then call `async_write_ha_state()`.
- The coordinator data structure is `dict[int, dict[int, str]]` — `{device_id: {attr_id: raw_value_string}}`. Entities parse raw strings to native types themselves.
- Entity unique IDs follow the pattern `{device_id}_{entity_key}`.
- Use `entity_registry_enabled_default = True` for well-known attributes, `False` for everything else.

## Testing

The `api.py` module has no Home Assistant dependencies and can be unit tested in isolation with mocked SOAP responses.

## Debugging Tips

- Add response body logging to `_send_request` in `api.py` when debugging SOAP issues.
- Config flow exception handlers should log the actual error, not just set `errors["base"]`.
- Check the HA logs for `VitotrolError` messages — they include the API's `ErgebnisText` error description.
