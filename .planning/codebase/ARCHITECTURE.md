# Architecture

**Analysis Date:** 2026-03-04

## Pattern Overview

**Overall:** Layered async Python integration for Home Assistant with clear dependency boundaries. Five-layer architecture (const → api → coordinator → entity → platforms) each depending only on layers below. All communication with the Viessmann SOAP API is isolated in `api.py` and accessed through `VitotrolCoordinator`, which acts as a data hub.

**Key Characteristics:**
- Pure async/await throughout — all network operations are non-blocking
- Dynamic attribute discovery via GetTypeInfo — supports all device attributes without hard-coding
- Optimistic state updates for write operations — UI responds immediately while write waits asynchronously
- Entity registry pre-seeding — coordinator polls only the attributes that entities actually need
- Automatic re-authentication on API errors — transparent retry without user intervention

## Layers

**Layer 1: Constants (`const.py`)**
- Purpose: Centralized configuration for SOAP API endpoints, polling intervals, wait parameters, and well-known attribute IDs
- Location: `custom_components/vitotrol/const.py`
- Contains: SOAP endpoint URL, namespace, API version strings, polling/wait timeouts, attribute ID constants
- Depends on: Nothing (pure configuration)
- Used by: All other layers

**Layer 2: SOAP API Client (`api.py`)**
- Purpose: Pure async SOAP client with no Home Assistant dependencies — can be tested standalone
- Location: `custom_components/vitotrol/api.py`
- Contains: `VitotrolAPI` class, `VitotrolDevice`, `VitotrolAuthError`, `VitotrolError`, `AttributeTypeInfo` dataclasses
- Depends on: `const.py`, aiohttp, defusedxml (standard library), no HA deps
- Used by: Coordinator, config flow
- Key responsibility: Manages session cookies over HA's shared `aiohttp.ClientSession`, implements async wait pattern (fire request → poll status → read results)

**Layer 3: Coordinator (`coordinator.py`)**
- Purpose: DataUpdateCoordinator that orchestrates polling, device discovery, attribute registration, and write operations
- Location: `custom_components/vitotrol/coordinator.py`
- Contains: `VitotrolCoordinator` class extending `DataUpdateCoordinator[dict[int, dict[int, str]]]`
- Depends on: `const.py`, `api.py`, `attributes.py` (ATTRIBUTE_REGISTRY), HA's update coordinator
- Used by: Platform entities, `__init__.py` for setup
- Key responsibility:
  - Discovers all device attributes via `GetTypeInfo` at startup
  - Pre-seeds polling set from entity registry (so first refresh polls registered entities only)
  - Manages per-entity attr_id registration — only registered attrs are polled
  - Handles re-authentication on both `VitotrolAuthError` and generic `VitotrolError`
  - Provides `async_write()` for platform entities with built-in re-auth retry

**Layer 4: Base Entity (`entity.py`)**
- Purpose: Common entity base class that all platform entities inherit from
- Location: `custom_components/vitotrol/entity.py`
- Contains: `VitotrolEntity(CoordinatorEntity)`, `entity_key_for_attr()`, `infer_unknown_metadata()` for dynamic attribute handling
- Depends on: `const.py`, `api.py`, `attributes.py`, HA's CoordinatorEntity
- Used by: All six platform modules (sensor, binary_sensor, climate, number, select, switch)
- Key responsibility:
  - Centralizes entity lifecycle (register/unregister attr_ids on add/remove)
  - Provides `_device_data` property for accessing raw attribute values
  - Provides `_update_coordinator_data()` for optimistic updates
  - Infers metadata (device class, unit, state class) for unknown attributes discovered at runtime

**Layer 5: Entity Platforms**
- Purpose: Platform-specific entity implementations
- Location: `custom_components/vitotrol/{sensor,binary_sensor,climate,number,select,switch}.py`
- Contains: Platform classes (`VitotrolSensor`, `VitotrolBinarySensor`, `VitotrolClimate`, `VitotrolNumber`, `VitotrolSelect`, `VitotrolSwitch`)
- Depends on: Layer 4 (entity.py), coordinator, attributes, HA platform classes
- Used by: Home Assistant platform setup system
- Special cases:
  - **Climate** (`climate.py`): Composite entity reading multiple attributes (current temp, target temp, operating mode, burner state, eco/party mode). One per device. Routes to one of multiple `CLIMATE_CONFIGS` based on device capability.
  - **All others**: Direct 1:1 mapping from attribute to entity. Support both known attributes (from `ATTRIBUTE_REGISTRY`) and unknown attributes (inferred metadata).

**Supporting Layer: Attributes Registry (`attributes.py`)**
- Purpose: Static registry of known attribute metadata — English names, platform routing, units, device classes, enum translations
- Location: `custom_components/vitotrol/attributes.py`
- Contains: `ATTRIBUTE_REGISTRY` (dict[int, AttrMeta]), `CLIMATE_CONFIGS` (list[ClimateMeta])
- Used by: Coordinator (pre-seed fallback), entity.py (infer unknown), all platforms
- Key concept: Known attributes are enabled by default; unknown attributes are disabled by default and inferred dynamically

**Configuration Layer (`config_flow.py`, `__init__.py`)**
- Purpose: Setup and lifecycle management
- Location: `custom_components/vitotrol/config_flow.py`, `custom_components/vitotrol/__init__.py`
- Config flow: Validates credentials, prompts for username/password, options for scan interval
- Setup entry: Creates API → logs in → discovers devices → creates coordinator → discovers attributes → pre-seeds from registry → performs first refresh → forwards to platforms

## Data Flow

**Initial Setup:**

1. User enters credentials in config flow → `VitotrolAPI.login()` → `VitotrolAPI.get_devices()`
2. Setup entry creates `VitotrolCoordinator` with device list
3. Coordinator calls `async_setup_type_info()` → for each device, calls `api.get_type_info()` → builds `_attribute_catalog`
4. Setup entry pre-seeds from entity registry: extracts enabled entities from HA's entity registry, maps to attr_ids, calls `coordinator.register_entity_attrs()`
5. First refresh via `async_config_entry_first_refresh()` → polls the registered attr_ids
6. Platforms setup: For each platform, iterate devices/attributes, create entities that call `register_entity_attrs()` on `async_added_to_hass()`

**Data Polling (continuous, every ~300s):**

1. Coordinator's `_async_update_data()` is called by HA
2. For each device, get the union of attr_ids from all registered entities
3. Fire `api.refresh_data_wait()` → waits 8s initial → polls status every 1s → timeout 60s → then `api.get_data()`
4. Collect results into `dict[int, dict[int, str]]` (device_id → {attr_id: raw_value_string})
5. Store in `coordinator.data`
6. All entities' property getters read from `_device_data` → parse strings to native types

**Write Operation (user turns on switch or changes temperature):**

1. Platform entity calls `coordinator.async_write(device, attr_id, value)`
2. Coordinator optionally updates `coordinator.data` immediately (optimistic update) → entity property reflects change instantly
3. Coordinator fires `api.write_data_wait()` asynchronously → waits 4s initial → polls status → timeout 60s
4. On failure, coordinator retries after re-login
5. Platform entity continues to use optimistic value; when next poll happens, confirmed value replaces it

**Error Handling:**

- `VitotrolAuthError` (login failed) → coordinator catches on any operation → re-logins → retries → if still fails, raises
- `VitotrolError` (any other API error) → coordinator catches on polling → re-logins once → retries → if still fails, raises as `UpdateFailed`
- Config flow catches errors and sets UI error messages

## State Management

**Coordinator Data Structure:** `dict[int, dict[int, str]]`
- Outer dict key: device_id (int)
- Inner dict key: attr_id (int)
- Inner dict value: raw value string from SOAP API (not parsed yet)

**Entity Registration:**
- `coordinator._entity_attr_ids: dict[int, dict[str, set[int]]]` → {device_id: {entity_unique_id: {attr_ids}}}
- Entities register themselves when `async_added_to_hass()` is called
- Coordinator computes polling set as union of all registered attr_ids per device
- Fallback (before entities are added): use `ATTRIBUTE_REGISTRY` enabled-by-default attributes

**Attribute Catalog:**
- `coordinator._attribute_catalog: dict[int, dict[int, AttributeTypeInfo]]` → {device_id: {attr_id: metadata}}
- Built once at setup via GetTypeInfo
- Never changed after setup
- Used to look up attribute names, types, min/max, enum values, readable/writable flags

## Key Abstractions

**VitotrolEntity:**
- Purpose: Base class for all entities, implements common lifecycle and data access
- Examples: `VitotrolSensor`, `VitotrolBinarySensor`, `VitotrolClimate`, etc.
- Pattern: All extend `CoordinatorEntity[VitotrolCoordinator]` and implement `_vitotrol_attr_id` (or override `_polling_attr_ids()` for multi-attr)

**VitotrolAPI:**
- Purpose: Encapsulate SOAP client logic, session management, async wait polling
- Pattern: No HA dependencies — pure async Python with aiohttp
- Methods follow WSDL exactly: `login()`, `get_devices()`, `get_type_info()`, `get_data()`, `refresh_data()`, `request_refresh_status()`, `refresh_data_wait()`, `write_data()`, `request_write_status()`, `write_data_wait()`

**AttributeTypeInfo:**
- Purpose: Metadata returned by GetTypeInfo
- Pattern: Immutable dataclass with all fields from WSDL response
- Key fields: attr_id, name (German), type, min/max values, unit, enum_values (dict[int, str] for value→label)

**AttrMeta / ATTRIBUTE_REGISTRY:**
- Purpose: Static metadata for known attributes (English names, platform routing, units, device classes, enum translations)
- Pattern: Single source of truth for known attribute configuration
- Used to: Route attributes to platforms, set units/device classes, translate enums to English, determine enabled-by-default

## Entry Points

**`__init__.py::async_setup_entry()`:**
- Location: `custom_components/vitotrol/__init__.py`
- Triggers: When user adds integration via UI
- Responsibilities:
  1. Create `VitotrolAPI` with credentials
  2. Login and get devices
  3. Create `VitotrolCoordinator`
  4. Discover attributes via `GetTypeInfo`
  5. Pre-seed from entity registry
  6. Perform first refresh
  7. Store runtime data
  8. Forward to platforms

**`config_flow.py::async_step_user()`:**
- Location: `custom_components/vitotrol/config_flow.py`
- Triggers: User selects integration in UI
- Responsibilities: Prompt for credentials, validate, create config entry

**`{platform}.py::async_setup_entry()`:**
- Location: `custom_components/vitotrol/{sensor,binary_sensor,climate,number,select,switch}.py`
- Triggers: After main integration setup, once per platform
- Responsibilities: Iterate devices/attributes, create platform entities, call `async_add_entities()`

## Error Handling

**Strategy:** Fail fast in setup, graceful retry on polling, transparent re-auth on failures

**Setup (`async_setup_entry`):**
- `VitotrolError` on login or `get_devices()` → raise `ConfigEntryNotReady` (HA will retry setup)
- `VitotrolError` on `get_type_info()` → raise `ConfigEntryNotReady`

**Polling (`_async_update_data`):**
- `VitotrolAuthError` → immediately re-login + retry → if still fails, raise `UpdateFailed`
- `VitotrolError` (other) → re-login once + retry → if still fails, raise `UpdateFailed`
- Generic exception → let it propagate as `UpdateFailed`

**Platform Writes (e.g., turn on switch):**
- Entity calls `coordinator.async_write()` which handles re-auth internally
- If write fails after retry, exception propagates to HA entity's async_turn_on/set_temperature/etc., logged as unavailability

## Cross-Cutting Concerns

**Logging:**
- Module: `import logging; _LOGGER = logging.getLogger(__name__)`
- Pattern: DEBUG for SOAP requests/responses, INFO for device discovery, WARNING for failures with fallback, ERROR for auth failures
- Key loggers: `vitotrol.api` (SOAP details), `vitotrol.coordinator` (polling/attr registration), `vitotrol` (setup/entity)

**Validation:**
- API layer: XML schema validation via defusedxml, SOAP Ergebnis code checking, element presence checks
- Platform layer: Attr value type conversion (string → float/int), availablity check (attr_id in _device_data)
- Coordinator: Attribute catalog presence check before polling

**Authentication:**
- API stores cookies in `_cookies` dict (over HA's session)
- Re-login on `VitotrolAuthError` or any `VitotrolError` during polling
- Config flow validates credentials before creation
- Reauth flow (`async_step_reauth`) prompts to update password when session expires

**Entity Lifecycle:**
- `async_added_to_hass()` → register attr_ids with coordinator (enables polling)
- `async_will_remove_from_hass()` → unregister attr_ids (stops polling if no other entities need them)
- Ensures coordinator only polls attributes that active entities use

---

*Architecture analysis: 2026-03-04*
