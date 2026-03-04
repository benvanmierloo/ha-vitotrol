# External Integrations

**Analysis Date:** 2026-03-04

## APIs & External Services

**Viessmann Vitotrol Cloud SOAP API:**
- Viessmann Vitotrol boiler control API (cloud-hosted service)
  - **Endpoint:** `https://vitotrolapp.viessmann-climatesolutions.com/app_vitodata/VIIWebService-1.16.0.0/iPhoneWebService.asmx`
  - **Namespace:** `http://www.e-controlnet.de/services/vii/`
  - **WSDL:** `https://vitotrolapp.viessmann-climatesolutions.com/app_vitodata/VIIWebService-1.16.0.0/iPhoneWebService.asmx?wsdl`
  - **SDK/Client:** Pure Python async SOAP client built in `api.py` (no SDK, direct HTTP SOAP)
  - **Auth:** Username/password credentials (stored in Home Assistant encrypted config)
  - **Credentials fields:** `Benutzer` (username), `Passwort` (password)
  - **Session management:** Cookie-based sessions (stored in `_cookies` dict in `api.py`)
  - **Location:** `custom_components/vitotrol/api.py`

**API Operations:**
- `Login()` - Authenticate and establish session cookie
  - Required fields: Benutzer, Passwort, Betriebssystem, AppId, AppVersion
  - App metadata: `APP_ID="prod"`, `APP_VERSION="4.3.1"`, `APP_OS="Android"`
  - Location: `custom_components/vitotrol/api.py:VitotrolAPI.login()`

- `GetDevices()` - Discover all locations and devices under account
  - Returns nested AnlageV2 (locations) → GeraetV2 (devices)
  - Location: `custom_components/vitotrol/api.py:VitotrolAPI.get_devices()`

- `GetTypeInfo(AnlageId, GeraetId)` - Discover all available datapoints for a device
  - Returns DatenpunktTypInfo entries with metadata (name, type, min/max, units, R/W flags, enum values)
  - Enum values encoded as `"ID-N"` format (e.g., `"92-0"`, `"92-1"`)
  - Location: `custom_components/vitotrol/api.py:VitotrolAPI.get_type_info()`

- `GetData(AnlageId, GeraetId, DatenpunktIds)` - Read cached attribute values
  - Returns current state for specified datapoints
  - Location: `custom_components/vitotrol/api.py:VitotrolAPI.get_data()`

- `RefreshData(AnlageId, GeraetId, DatenpunktIds)` - Trigger device to upload fresh data (async)
  - Returns AktualisierungsId (refresh ID) for polling
  - Initial wait: 8 seconds before polling status
  - Location: `custom_components/vitotrol/api.py:VitotrolAPI.refresh_data()`

- `RequestRefreshStatus(AktualisierungsId)` - Poll refresh operation status
  - Status 0 = pending, 1/3 = in progress, 4/9 = success
  - Location: `custom_components/vitotrol/api.py:VitotrolAPI.request_refresh_status()`

- `WriteData(AnlageId, GeraetId, DatapointId, Wert)` - Write value to device attribute (async)
  - Value format: string (server parses per attribute type)
  - Whole numbers: NO decimal point (e.g., `"20"` not `"20.0"`)
  - Decimals: use period separator (e.g., `"20.5"`)
  - Location: `custom_components/vitotrol/api.py:VitotrolAPI.write_data()`

- `RequestWriteStatus(AktualisierungsId)` - Poll write operation status
  - Same status semantics as RefreshData
  - Location: `custom_components/vitotrol/api.py:VitotrolAPI.request_write_status()`

**API Constraints (CRITICAL):**
- **Session lifetime unknown** - Vitotrol server may expire sessions unpredictably
- **Re-auth strategy:** Login once at setup, re-login + retry on ANY API error (both 401 and other errors)
- **Unsupported attributes crash requests** - Requesting an attribute not returned by GetTypeInfo fails entire SOAP call
- **Response validation:** All SOAP responses include `<Ergebnis>` (result code, 0=success) and `<ErgebnisText>` (error message)
- **SOAP envelope structure:** Must match WSDL element order (AnlageId before GeraetId)
- **Async operations:** RefreshData and WriteData are slow (8-15 seconds to complete due to polling wait times)

## Data Storage

**Databases:**
- None - This is a polling integration with no persistent storage
- Data stored in Home Assistant's entity registry and coordinator cache only

**File Storage:**
- None - Integration uses no external file storage

**Caching:**
- In-memory caching via DataUpdateCoordinator
  - Coordinate type: `dict[int, dict[int, str]]` → `{device_id: {attr_id: raw_value_string}}`
  - Location: `custom_components/vitotrol/coordinator.py:VitotrolCoordinator`

## Authentication & Identity

**Auth Provider:**
- Custom (Viessmann Vitotrol cloud credentials)
  - Username and password stored encrypted in Home Assistant config storage
  - Cookie-based session management (HTTP `Set-Cookie` header)
  - Location: `custom_components/vitotrol/api.py:VitotrolAPI` (lines 100-109)

**Re-authentication:**
- Triggered automatically by Home Assistant when API returns auth error
- Config flow re-auth step: `custom_components/vitotrol/config_flow.py:VitotrolConfigFlow.async_step_reauth()`
- User must re-enter password in Home Assistant UI

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service integrated

**Logs:**
- Python standard logging via `logging.getLogger(__name__)`
- Debug level: Full attribute catalogs logged as JSON (coordinator.py)
- Warning/Error level: API failures, auth errors, connection issues
- Location: Throughout codebase with `_LOGGER` instances

## CI/CD & Deployment

**Hosting:**
- GitHub repository (published to HACS community repository)
- Custom component installed via Home Assistant UI or HACS package manager

**CI Pipeline:**
- **hassfest validation** - GitHub Actions, validates manifest.json and Home Assistant compatibility
  - Workflow: `.github/workflows/hassfest.yaml`
- **HACS validation** - GitHub Actions, validates HACS repository requirements
  - Workflow: `.github/workflows/hacs.yaml`
  - Runs on: push to main, pull requests, daily schedule

## Environment Configuration

**Required env vars:**
- None - Integration uses Home Assistant's secure config storage

**Credentials storage:**
- Home Assistant encrypted secrets storage (via config entries)
  - Retrieved at setup time and stored in `VitotrolRuntimeData.api`

**Configuration entry keys:**
- `CONF_USERNAME` (homeassistant.const)
- `CONF_PASSWORD` (homeassistant.const)
- `CONF_SCAN_INTERVAL` (polling frequency, default 300s, range 60-900s)

**Default polling interval:**
- 300 seconds (5 minutes) - Configurable via Home Assistant UI options flow

## Webhooks & Callbacks

**Incoming:**
- None - Integration is polling-only (not event-driven)

**Outgoing:**
- None - No webhook calls made to external services

## Data Flow

**Polling Loop:**
1. Setup: `__init__.py:async_setup_entry()` creates API client and coordinator
2. Type discovery: Coordinator calls `api.get_type_info()` for all devices to discover available attributes
3. Pre-seed: Entity registry checked to determine which attributes were previously enabled
4. Refresh: Coordinator fires `api.refresh_data_wait()` → `api.get_data()` on polling interval
5. Parse: Entity platforms parse raw string values to native types (temperature, enum, boolean, etc.)
6. Write operations:
   - Entity calls `api.write_data_wait()` with new value
   - Updates local entity state optimistically
   - API polls for completion (0-15s wait)

---

*Integration audit: 2026-03-04*
