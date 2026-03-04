# Testing Patterns

**Analysis Date:** 2025-03-04

## Test Framework

**Runner:**
- pytest with pytest-homeassistant-custom-component plugin
- Version: pytest-homeassistant-custom-component==0.13.316
- Config: `pytest.ini`
- Async mode: auto (asyncio_mode = auto)
- Test paths: `tests/` directory

**Assertion Library:**
- pytest assertions (plain `assert` statements)
- HA-specific assertions via test utilities

**Run Commands:**
```bash
pytest tests/                  # Run all tests
pytest tests/test_sensor.py   # Run specific test file
pytest -v                      # Verbose output
pytest --cov                   # Coverage report
```

## Test File Organization

**Location:**
- Co-located with source: test files in separate `tests/` directory (not src-adjacent)
- One test file per platform/module: `test_sensor.py`, `test_coordinator.py`, `test_config_flow.py`

**Naming:**
- Test modules: `test_*.py`
- Test functions: `async def test_*()` for async tests, `def test_*()` for sync
- Helper functions: private prefix `_` or shared in conftest

**Structure:**
```
tests/
├── conftest.py           # Shared fixtures and mocks
├── test_init.py          # Integration setup/teardown
├── test_config_flow.py   # Config flow + options flow
├── test_coordinator.py   # DataUpdateCoordinator behavior
├── test_sensor.py        # Sensor platform
├── test_switch.py        # Switch platform
├── test_binary_sensor.py # Binary sensor platform
├── test_number.py        # Number platform
├── test_select.py        # Select platform
├── test_climate.py       # Climate platform
├── test_attributes.py    # Attribute registry
├── test_entity_helpers.py # Entity base class helpers
└── test_diagnostics.py   # Diagnostics
```

## Test Structure

**Suite Organization:**
All tests use pytest fixtures from `conftest.py`. Tests are organized by feature/platform, not by test type.

**Fixtures in `conftest.py`:**

```python
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return enable_custom_integrations

@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with test credentials."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "secret",
        },
        options={CONF_SCAN_INTERVAL: 300},
        unique_id="user@example.com",
    )

@pytest.fixture
def mock_api() -> Generator[MagicMock, None, None]:
    """Patch VitotrolAPI so no real HTTP calls are made."""
    mock_cls = MagicMock()
    instance = mock_cls.return_value
    instance.login = AsyncMock()
    instance.get_devices = AsyncMock(return_value=[FAKE_DEVICE])
    instance.get_type_info = AsyncMock(return_value={5373: FAKE_ATTR_INFO})
    instance.refresh_data_wait = AsyncMock(return_value=None)
    instance.get_data = AsyncMock(return_value={5373: "12.5"})
    instance.write_data_wait = AsyncMock()

    with patch(
        "custom_components.vitotrol.config_flow.VitotrolAPI",
        mock_cls,
    ), patch(
        "custom_components.vitotrol.VitotrolAPI",
        mock_cls,
    ):
        yield mock_cls
```

**Patterns:**
- **Setup:** Fixture-driven with `mock_api` and `mock_config_entry` auto-configured
- **Load integration:** Helper function `async def _load(hass: HomeAssistant, entry: MockConfigEntry)`
- **Assertions:** Direct state checks via `hass.states.get(entity_id)`
- **Async handling:** All async test functions marked with `async def`

**Example test from `test_sensor.py`:**
```python
async def test_outdoor_temp_sensor_value(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Outdoor temperature sensor reflects coordinator data."""
    await _load(hass, mock_config_entry)

    state = hass.states.get("sensor.vitovalor_300_p_outdoor_temperature")
    assert state is not None
    assert state.state == "12.5"
```

## Mocking

**Framework:** `unittest.mock` (MagicMock, AsyncMock, patch)

**Patterns:**

Mock API returns default values, overridden per test:
```python
# Global mock in conftest.py
instance.login = AsyncMock()
instance.get_devices = AsyncMock(return_value=[FAKE_DEVICE])
instance.get_type_info = AsyncMock(return_value={5373: FAKE_ATTR_INFO})
instance.get_data = AsyncMock(return_value={5373: "12.5"})

# Override in test for specific behavior
async def test_enum_sensor_returns_label(hass, mock_api, mock_config_entry) -> None:
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={708: FAKE_OPERATING_MODE_STATUS_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={708: "2"})
```

Mock errors for error scenarios:
```python
# VitotrolAuthError in test_coordinator.py
async def test_auth_error_triggers_relogin_and_succeeds(hass: HomeAssistant) -> None:
    api = AsyncMock()
    api.login = AsyncMock()
    api.refresh_data_wait = AsyncMock(return_value=None)
    api.get_data = AsyncMock(
        side_effect=[VitotrolAuthError("expired"), {5373: "11.0"}]
    )
    # ... test retries after re-login
```

**What to Mock:**
- API calls (VitotrolAPI methods)
- External HTTP (via mock_api fixture)
- HA entity registry (via MockConfigEntry)

**What NOT to Mock:**
- Coordinator logic (test the actual coordinator)
- Entity state computations (test actual properties)
- Data transformations (test actual conversion)
- HA framework calls (use pytest-homeassistant utilities)

## Fixtures and Factories

**Test Data:**
Constants defined at module level in `conftest.py`:

```python
FAKE_DEVICE = VitotrolDevice(
    device_id=1001,
    device_name="Vitovalor 300-P",
    location_id=2001,
    location_name="Home",
    has_error=False,
    is_connected=True,
)

FAKE_ATTR_INFO = AttributeTypeInfo(
    attr_id=5373,
    name="Temp_Aussen",
    type="Double",
    type_value=3,
    min_value=-50.0,
    max_value=70.0,
    unit="°C",
    group="Temperaturen",
    readable=True,
    writable=False,
    factory_default=None,
    heating_circuit_id=None,
    enum_values=None,
)

FAKE_COORDINATOR_DATA = {
    FAKE_DEVICE.device_id: {
        5373: "12.5",  # outdoor temp
    }
}
```

Test-specific fixtures created in test files:
```python
# test_sensor.py
FAKE_OPERATING_MODE_STATUS_INFO = AttributeTypeInfo(
    attr_id=708,
    name="Betriebsart_Ist",
    type="ENUM",
    # ... configured for specific test scenario
)
```

**Location:**
- Shared fixtures: `tests/conftest.py`
- Test-specific fake data: top of test module file
- Helper functions: `conftest.py` with underscore prefix

## Coverage

**Requirements:** Not enforced (no pytest-cov configuration visible)

**View Coverage:**
```bash
pytest --cov=custom_components.vitotrol tests/
pytest --cov=custom_components.vitotrol --cov-report=html tests/
```

## Test Types

**Unit Tests (majority):**
- Scope: Individual methods or small components
- Approach: Mock external dependencies, test logic in isolation
- Example: `test_coordinator.py::test_successful_update()` tests coordinator's `_async_update_data()` with mock API

**Integration Tests:**
- Scope: Full setup flow from config_flow → coordinator → entity platforms
- Approach: Use `_load(hass, entry)` helper to trigger `async_setup_entry()`
- Example: `test_sensor.py::test_outdoor_temp_sensor_value()` loads integration and checks entity state reflects coordinator data
- HA utilities provide test hass instance with real entity registry, state machine, etc.

**E2E Tests:**
- Framework: Not used (no e2e test files)
- Would require: Real SOAP API credentials (infeasible for CI/CD)

## Common Patterns

**Async Testing:**
All tests involving HA integration are async. Pattern:

```python
async def test_feature(hass: HomeAssistant, mock_api, mock_config_entry) -> None:
    """Test description."""
    # Setup: Configure fixtures
    mock_api.return_value.some_method = AsyncMock(return_value=expected_value)

    # Execute: Call the code under test
    await _load(hass, mock_config_entry)  # Or: await coordinator._async_update_data()

    # Assert: Check results
    state = hass.states.get("sensor.entity_id")
    assert state.state == expected_value
```

**Error Testing:**
Coordinator handles auth errors with re-login retry:

```python
async def test_auth_error_triggers_relogin_and_succeeds(hass: HomeAssistant) -> None:
    """On VitotrolAuthError the coordinator re-logs in and retries."""
    api = AsyncMock()
    api.login = AsyncMock()
    api.refresh_data_wait = AsyncMock(return_value=None)
    api.get_data = AsyncMock(
        side_effect=[VitotrolAuthError("expired"), {5373: "11.0"}]
    )

    coord = _make_coordinator(hass, api)
    _seed_coordinator(coord)

    data = await coord._async_update_data()

    assert api.login.call_count == 1  # Re-login was called
    assert data[FAKE_DEVICE.device_id][5373] == "11.0"  # Retry succeeded
```

**State/Value Testing:**
Entity platform tests check raw → converted values:

```python
async def test_set_value_writes_integer(hass: HomeAssistant, mock_api, mock_config_entry) -> None:
    """Number entity converts float to integer and writes via coordinator."""
    mock_api.return_value.get_type_info = AsyncMock(...)
    mock_api.return_value.get_data = AsyncMock(return_value={51: "50"})

    await _load(hass, mock_config_entry)

    entity_id = "number.vitovalor_300_p_hot_water_setpoint"
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: entity_id, "value": 55.7},
        blocking=True,
    )

    # Check coordinator data was updated
    mock_api.return_value.write_data_wait.assert_called_once()
```

**Config Flow Testing:**
Tests use flow context and step navigation:

```python
async def test_user_flow_success(hass: HomeAssistant, mock_api) -> None:
    """Complete setup via user step creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "user@example.com"
```

## Test Organization Strategy

**By Feature (current approach):**
- `test_sensor.py` — All sensor-specific logic
- `test_switch.py` — All switch-specific logic
- `test_coordinator.py` — Polling, error handling, re-login
- `test_config_flow.py` — Setup, options, reauth flows
- `test_init.py` — Integration lifecycle

**Test Count (14 files, ~80+ test functions):**
- Coordinator: 7 tests (update, error, retry)
- Config flow: 8 tests (user, reauth, options flows)
- Sensor: 4+ tests (known attr, unknown attr, enum mapping)
- Switch: 4+ tests (on/off, write, unknown inferred)
- Number: 5+ tests (value, limits, write, invalid data)
- Binary sensor: 3+ tests (on/off, unknown inferred)
- Select: 4+ tests (state, options, write, unknown inferred)
- Climate: 5+ tests (temp, hvac mode, preset)
- Entity helpers: 3+ tests (metadata inference, key generation)
- Attributes: 3+ tests (registry validation)
- Diagnostics: 2+ tests (redaction, device info)
- Init: 3+ tests (setup, unload, error handling)

---

*Testing analysis: 2025-03-04*
