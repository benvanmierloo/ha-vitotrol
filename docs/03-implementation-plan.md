# Implementation Plan

## Phase 1: Foundation

### Step 1.1 — `const.py`
Define all constants used across the integration:
- `DOMAIN = "vitotrol"`
- `PLATFORMS` list: `sensor`, `binary_sensor`, `climate`, `switch`, `number`
- `DEFAULT_SCAN_INTERVAL = 60`
- All attribute ID constants (e.g., `ATTR_INDOOR_TEMP = 5367`)
- `ALL_READABLE_ATTRIBUTES` list — every attribute ID we attempt to poll
- Enum value mappings for operating mode, valve status, etc.

### Step 1.2 — `api.py`
Port the go-vitotrol SOAP client to async Python:

**Classes**:
- `VitotrolError(Exception)` — general API error
- `VitotrolAuthError(VitotrolError)` — authentication failure
- `VitotrolDevice` — dataclass with location/device IDs, names, status flags

**`VitotrolAPI` class**:
- `__init__(self, username, password, session)` — takes HA's shared aiohttp session
- `async login()` — SOAP Login, store cookies in private dict
- `async get_devices()` — SOAP GetDevices, return list of VitotrolDevice
- `async get_data(device, attr_ids)` — SOAP GetData, return `{attr_id: value_str}`
- `async refresh_data(device, attr_ids)` — SOAP RefreshData, return refresh_id
- `async request_refresh_status(refresh_id)` — SOAP RequestRefreshStatus, return status int
- `async refresh_data_wait(device, attr_ids)` — RefreshData + poll until done
- `async write_data(device, attr_id, value)` — SOAP WriteData, return refresh_id
- `async request_write_status(refresh_id)` — SOAP RequestWriteStatus, return status int
- `async write_data_wait(device, attr_id, value)` — WriteData + poll until done
- `_send_request(soap_action, body)` — internal: build SOAP envelope, send POST,
  parse XML, strip namespaces, check ResultHeader, return parsed Element

**XML handling**:
- Build request XML with string formatting (the SOAP messages are simple enough)
- Parse responses with `xml.etree.ElementTree`
- Strip XML namespaces from response for easy traversal
- Cookie management: store in `self._cookies` dict, pass as `Cookie` header

**Testing considerations**:
- The API class has no HA dependencies, making it unit-testable in isolation
- SOAP responses can be mocked with static XML strings

### Step 1.3 — `manifest.json`
Already created. Contains:
- `domain`, `name`, `version`
- `config_flow: true`
- `iot_class: cloud_polling`
- `codeowners: ["@benvanmierloo"]`
- No external `requirements` (uses stdlib + aiohttp from HA)

---

## Phase 2: Integration Wiring

### Step 2.1 — `coordinator.py`
**`VitotrolCoordinator(DataUpdateCoordinator)`**:
- `__init__`: store api reference, device list, scan interval, attr tracking state
- `_async_update_data`:
  1. For each device in the device list:
     a. Try `api.refresh_data_wait(device, self._supported_attrs[device_id])`
     b. On failure: log warning, continue to GetData anyway (cached data is ok)
     c. `api.get_data(device, self._supported_attrs[device_id])`
     d. Store results in data dict
  2. On complete failure (e.g., session expired):
     a. Re-login: `await api.login()`
     b. Retry the entire update once
     c. If still fails: `raise UpdateFailed`
  3. Attribute discovery (first run only):
     - Start with `ALL_READABLE_ATTRIBUTES`
     - After GetData, note which attr_ids actually returned data
     - On subsequent runs, only request those that worked
  4. Return `{device_id: {attr_id: value_str}}`

### Step 2.2 — `config_flow.py`
**`VitotrolConfigFlow(ConfigFlow, domain=DOMAIN)`**:
- `async_step_user(user_input)`:
  1. Show form with `username` (email) and `password` fields
  2. On submit: create temporary API, call `login()` + `get_devices()`
  3. On auth failure → show `invalid_auth` error
  4. On connection failure → show `cannot_connect` error
  5. On no devices → show `no_devices` error
  6. Set `unique_id` to username, abort if already configured
  7. Create config entry with `data={username, password}`

**`VitotrolOptionsFlow(OptionsFlow)`**:
- `async_step_init(user_input)`:
  1. Show form with `scan_interval` (int, 30-600, default from current options or 60)
  2. On submit: save options, coordinator picks up change via listener

### Step 2.3 — `__init__.py`
**`async_setup_entry(hass, entry)`**:
1. `session = async_get_clientsession(hass)`
2. `api = VitotrolAPI(username, password, session)`
3. `await api.login()` — wrap in try/except, raise `ConfigEntryNotReady` on failure
4. `devices = await api.get_devices()`
5. `coordinator = VitotrolCoordinator(hass, api, devices, scan_interval)`
6. `await coordinator.async_config_entry_first_refresh()`
7. `hass.data[DOMAIN][entry.entry_id] = {"api": api, "coordinator": coordinator, "devices": devices}`
8. `await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)`
9. Register options update listener to restart on scan_interval change

**`async_unload_entry(hass, entry)`**:
1. `await hass.config_entries.async_unload_platforms(entry, PLATFORMS)`
2. `hass.data[DOMAIN].pop(entry.entry_id)`

### Step 2.4 — `entity.py`
**`VitotrolEntity(CoordinatorEntity)`**:
- `__init__(coordinator, device, key)`:
  - `self._device_id = device.device_id`
  - `self._attr_unique_id = f"{device.device_id}_{key}"`
  - `self._attr_has_entity_name = True`
  - `self._attr_device_info = DeviceInfo(...)`
- `_device_data` property → `coordinator.data.get(device_id, {})`
- `_get_attr_value(attr_id)` → returns raw string value or None

---

## Phase 3: Entity Platforms

### Step 3.1 — `sensor.py`
Define `VitotrolSensorEntityDescription(SensorEntityDescription)`:
- Extra field: `attr_id: int`
- Extra field: `enum_values: dict[str, str] | None` — for enum-type sensors

Define `SENSOR_DESCRIPTIONS` tuple with all sensor entity descriptions.

**`VitotrolSensor(VitotrolEntity, SensorEntity)`**:
- `native_value` property:
  - For temperature/double sensors: `float(raw_value)`
  - For enum sensors: look up `raw_value` in `enum_values` dict
  - For string sensors: return raw string

**`async_setup_entry`**:
- Iterate devices × sensor descriptions
- Only create entity if the attr_id exists in coordinator.data for that device

### Step 3.2 — `binary_sensor.py`
Define `VitotrolBinarySensorEntityDescription(BinarySensorEntityDescription)`:
- Extra field: `attr_id: int`
- Extra field: `on_values: tuple[str, ...]` — values that mean "on"

Define `BINARY_SENSOR_DESCRIPTIONS` tuple.

**`VitotrolBinarySensor(VitotrolEntity, BinarySensorEntity)`**:
- `is_on` property: `raw_value in description.on_values`

### Step 3.3 — `climate.py`
**`VitotrolClimate(VitotrolEntity, ClimateEntity)`**:

Properties:
- `hvac_modes`: `[OFF, AUTO, HEAT]`
- `preset_modes`: `[NONE, ECO, BOOST]`
- `current_temperature`: read IndoorTemp
- `target_temperature`: read HeatNormalTemp
- `hvac_mode`: map OperatingModeRequested value → OFF/AUTO/HEAT
- `hvac_action`: derive from BurnerState + OperatingModeCurrent
- `preset_mode`: derive from EnergySavingMode + PartyMode
- `min_temp`: 3
- `max_temp`: 30
- `target_temperature_step`: 0.5
- `temperature_unit`: CELSIUS
- `supported_features`: TARGET_TEMPERATURE | PRESET_MODE

Actions:
- `async_set_temperature(**kwargs)`:
  - `await api.write_data_wait(device, ATTR_HEAT_NORMAL_TEMP, str(temp))`
  - Optimistic update + `async_write_ha_state()`
- `async_set_hvac_mode(hvac_mode)`:
  - Map OFF→"0", AUTO→"2", HEAT→"4"
  - `await api.write_data_wait(device, ATTR_OPERATING_MODE_REQUESTED, value)`
  - Optimistic update
- `async_set_preset_mode(preset_mode)`:
  - NONE: write EnergySavingMode="0", PartyMode="0"
  - ECO: write EnergySavingMode="1"
  - BOOST: write PartyMode="1"
  - Optimistic update

### Step 3.4 — `switch.py`
**`VitotrolSwitch(VitotrolEntity, SwitchEntity)`**:

Two instances per device: party_mode, energy_saving_mode.

- `is_on`: `raw_value == "1"`
- `async_turn_on()`: `write_data_wait(device, attr_id, "1")`, optimistic update
- `async_turn_off()`: `write_data_wait(device, attr_id, "0")`, optimistic update
- Entity category: CONFIG

### Step 3.5 — `number.py`
Define `VitotrolNumberEntityDescription(NumberEntityDescription)`:
- Extra field: `attr_id: int`

Three instances per device: hot_water_setpoint, reduced_temperature, party_mode_temperature.

**`VitotrolNumber(VitotrolEntity, NumberEntity)`**:
- `native_value`: `float(raw_value)`
- `async_set_native_value(value)`: `write_data_wait(device, attr_id, str(value))`, optimistic update
- Entity category: CONFIG

---

## Phase 4: Translations & Metadata

### Step 4.1 — `strings.json`
Config flow strings: step titles, field labels, error messages, abort reasons.

### Step 4.2 — `translations/en.json`
Full English translations including:
- Config flow strings (same as strings.json)
- Options flow strings
- Entity names for all platforms (sensor, binary_sensor, climate, switch, number)

### Step 4.3 — `diagnostics.py`
Simple diagnostics that dumps:
- Config entry data (with password redacted)
- Coordinator data (all attribute values)
- Device information

### Step 4.4 — `hacs.json` (repo root)
HACS metadata for easy installation via HACS.

---

## Phase 5: Quality & Polish

### Step 5.1 — Testing
- Verify config flow: login success, login failure, no devices
- Verify coordinator: data polling, re-auth on error, attribute discovery
- Verify entity state mapping: correct values, correct availability
- Verify write operations: climate, switch, number entities
- Verify multiple devices under one account

### Step 5.2 — Edge Cases to Handle
1. Device not connected (`is_connected=false`) → entities show unavailable
2. API session expires mid-poll → re-login + retry
3. Unsupported attribute for device model → exclude from future polls
4. Slow API responses → coordinator handles via async wait, HA stays responsive
5. Network timeout → `UpdateFailed`, retry on next interval
6. Multiple devices under one account → separate device entries, shared coordinator

### Step 5.3 — Future Enhancements (not in v1)
- `select` entity for fine-grained operating mode control (all 5 modes)
- `water_heater` entity for DHW control
- Timesheet/schedule entities
- Custom attribute support (like the `NAME_0xNNNN` pattern from Go)
- Error history as events or persistent notifications
- `ComputedSetpointTemp` as a template sensor

---

## Dependency Graph

```
const.py          ← no dependencies (pure constants)
    ▲
    │
api.py            ← depends on: const.py (attribute IDs)
    ▲
    │
coordinator.py    ← depends on: api.py, const.py
    ▲
    │
entity.py         ← depends on: coordinator.py, const.py
    ▲
    │
__init__.py       ← depends on: api.py, coordinator.py, const.py
config_flow.py    ← depends on: api.py, const.py
    ▲
    │
sensor.py         ← depends on: entity.py, const.py
binary_sensor.py  ← depends on: entity.py, const.py
climate.py        ← depends on: entity.py, const.py
switch.py         ← depends on: entity.py, const.py
number.py         ← depends on: entity.py, const.py
diagnostics.py    ← depends on: const.py
```

## Implementation Order

Write files in this order (respecting dependencies):

1. `const.py`
2. `api.py`
3. `coordinator.py`
4. `entity.py`
5. `config_flow.py`
6. `__init__.py`
7. `sensor.py`, `binary_sensor.py` (parallel)
8. `climate.py`, `switch.py`, `number.py` (parallel)
9. `strings.json`, `translations/en.json`, `diagnostics.py`, `hacs.json` (parallel)
