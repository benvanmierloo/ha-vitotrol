# Phase 1: Code Quality - Research

**Researched:** 2026-03-04
**Domain:** Home Assistant custom component — write operations, error patterns, pytest coverage
**Confidence:** HIGH (all findings based on direct code inspection + HA documentation)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Optimistic rollback (BUGS-01):** Capture pre-write value, revert immediately on exception — no coordinator refresh on failure
- **Value formatting (BUGS-02):** Strip `.0` for integers; preserve decimals; period as separator
- **Step size (BUGS-03):** Derive from GetTypeInfo metadata (`DatenpunktTyp`); default 1.0 (int) or 0.5 (temperature)
- **Preset write guard (BUGS-04):** Check `writable` flag; skip read-only with warning log; no user-facing error
- **Write error surfacing (BUGS-05):** `HomeAssistantError` for API/network failures; `ServiceValidationError` for validation (value out of range)
- **Auth failure (BUGS-06):** When re-auth retry also raises `VitotrolAuthError`, raise `ConfigEntryAuthFailed`
- **Empty catalog (BUGS-07):** Zero attrs → log warning + raise `ConfigEntryNotReady`
- **Coordinator constructor (HAPAT-01):** Add `config_entry: ConfigEntry` param; pass to `DataUpdateCoordinator.__init__`
- **Config flow strings (HAPAT-02):** Verify `no_devices` string in strings.json and translations/en.json

### Claude's Discretion

- Exact error message wording for `HomeAssistantError` (descriptive, format flexible)
- Step size default for temperature attrs if GetTypeInfo doesn't specify precision (0.5 recommended)
- Internal refactor approach for wrapping write methods (helper vs inline try/except)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BUGS-01 | Revert entity state to actual device value when WriteData fails or times out | Rollback pattern documented in code context; `_get_attr_value` + `_update_coordinator_data` are the primitives |
| BUGS-02 | WriteData value formatted correctly — strip `.0` suffix for integers, preserve decimals | `api.py:write_data` already partially implements this but strips ALL decimals; fix needed for non-integer values |
| BUGS-03 | Number entity step size derived from GetTypeInfo metadata instead of hardcoded `1.0` | `AttributeTypeInfo.type` field ("Double" vs "Integer") is available at entity construction; min/max already used |
| BUGS-04 | Climate preset writes check `writable` flag before attempting write to eco/party attrs | `AttributeTypeInfo.writable` bool available; attribute catalog accessible via `coordinator.get_attribute_catalog()` |
| BUGS-05 | All entity write operations raise `HomeAssistantError` or `ServiceValidationError` on failure | HA exception pattern verified; 4 write sites: climate.py, switch.py, number.py, select.py |
| BUGS-06 | Authentication failures raise `ConfigEntryAuthFailed`, triggering HA's reauth flow | `ConfigEntryAuthFailed` is a real HA exception; coordinator already has the retry logic structure |
| BUGS-07 | Empty GetTypeInfo catalog logs warning and raises `ConfigEntryNotReady` | `async_setup_type_info()` in coordinator.py is the correct injection point |
| HAPAT-01 | `VitotrolCoordinator` receives `config_entry` constructor parameter | `DataUpdateCoordinator.__init__` accepts `config_entry` kwarg; current code omits it |
| HAPAT-02 | Config flow surfaces distinct error messages | `no_devices` string ALREADY EXISTS in strings.json — nothing to add; translations/en.json needs verification |
| TEST-02 | Test: optimistic state rollback when WriteData raises exception | No such test exists; write pattern in entity files is uncovered |
| TEST-03 | Test: GetTypeInfo response with malformed/empty enum values | No such test exists; `get_type_info()` parsing in api.py uncovered for edge cases |
| TEST-04 | Test: config flow behavior when GetDevices returns empty device list | `test_config_flow.py` exists but `no_devices` path coverage needs verification |
| TEST-05 | Test: concurrent write operations completing independently | No concurrency test exists |
</phase_requirements>

## Summary

Phase 1 is a focused bug-fix and test-coverage phase. All changes are within the existing integration — no new dependencies are required. The codebase is well-structured: bugs are localized and the fix points are clear from reading the source.

The largest effort is in the four entity write methods (climate, switch, number, select) which all need the same pattern: capture old value, attempt write, on exception restore old value and raise `HomeAssistantError`. This is a mechanical change across 4 files with a consistent shape.

One important finding: **BUGS-02 (value formatting) is already partially fixed in `api.py:write_data`** — the existing code strips `.0` via `str(int(float(value)))` for any value containing a `.`. The bug is that it also truncates legitimate decimals like `"20.5"` to `"20"`. The fix is to strip trailing `.0` only when the decimal part is zero, not unconditionally.

**HAPAT-02 is already done:** `no_devices` error string exists in both `strings.json` and (likely) `translations/en.json`. The planner task should verify the translations file but not assume work is needed.

**Primary recommendation:** Implement BUGS fixes first (they are interdependent in the rollback pattern), then write tests that exercise the new behavior, then address HAPAT items which are independent.

## Standard Stack

### Core (already in use — no new dependencies)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `homeassistant` | installed in venv | Core HA exceptions, coordinator, entities | Use `ConfigEntryAuthFailed`, `ConfigEntryNotReady`, `HomeAssistantError`, `ServiceValidationError` |
| `pytest-homeassistant-custom-component` | installed in venv | Test framework for HA integrations | Already in use; 112 tests pass |
| `pytest-asyncio` | via above | Async test support | `asyncio_mode = auto` already set in pytest.ini |

### HA Exception Imports (verified from HA source)

```python
# For coordinator auth failure (BUGS-06)
from homeassistant.config_entries import ConfigEntryAuthFailed

# For empty catalog (BUGS-07)
from homeassistant.exceptions import ConfigEntryNotReady

# For entity write failures (BUGS-05)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
```

`ConfigEntryAuthFailed` is already imported in `__init__.py` does not exist yet in `coordinator.py` imports — must be added.

### No New Packages Required

All fixes use the existing HA framework patterns. The test suite uses
`pytest-homeassistant-custom-component` which is already installed and working.

**Run tests:**
```bash
.venv/bin/python -m pytest tests/ -x -q
```

## Architecture Patterns

### Pattern 1: Optimistic Write with Rollback (BUGS-01 + BUGS-05)

The current write pattern (without rollback or error surfacing):

```python
# Current (broken) pattern in switch.py, climate.py, number.py, select.py:
await self.coordinator.async_write(self._device, self._vitotrol_attr_id, "1")
self._update_coordinator_data(self._vitotrol_attr_id, "1")
self.async_write_ha_state()
```

The corrected pattern (rollback + HomeAssistantError):

```python
# Correct pattern — implement in all four platforms:
from homeassistant.exceptions import HomeAssistantError

old_value = self._get_attr_value(self._vitotrol_attr_id)
try:
    await self.coordinator.async_write(self._device, self._vitotrol_attr_id, "1")
except Exception as err:
    # Restore pre-write state immediately (don't wait for next poll)
    if old_value is not None:
        self._update_coordinator_data(self._vitotrol_attr_id, old_value)
    self.async_write_ha_state()
    raise HomeAssistantError(
        f"Failed to write {attr_name} (attr {self._vitotrol_attr_id}): {err}"
    ) from err
self._update_coordinator_data(self._vitotrol_attr_id, "1")
self.async_write_ha_state()
```

**Key insight:** `_update_coordinator_data` is currently called AFTER `async_write`. Since `async_write` can raise, the optimistic update may never be applied — leaving state stale until the next poll. The rollback pattern requires explicitly restoring the old value when the write fails.

**Climate `async_set_preset_mode` complexity:** This method calls `async_write` multiple times (disable old preset, enable new one). The rollback must capture all attrs that may be modified:

```python
# Multi-write rollback — capture all potentially-changed values first:
old_eco = self._get_attr_value(eco_attr)
old_party = self._get_attr_value(party_attr)
try:
    ...all writes...
except Exception as err:
    # Restore both attrs
    if eco_attr and old_eco is not None:
        self._update_coordinator_data(eco_attr, old_eco)
    if party_attr and old_party is not None:
        self._update_coordinator_data(party_attr, old_party)
    self.async_write_ha_state()
    raise HomeAssistantError(...) from err
```

### Pattern 2: Value Formatting Fix (BUGS-02)

Current `api.py:write_data` implementation (line 287):

```python
wire_value = str(int(float(value))) if "." in value else value
```

This converts `"20.5"` → `"20"` (wrong — truncates decimals).

Correct implementation:

```python
def _format_wire_value(value: str) -> str:
    """Format value for SOAP WriteData.

    Server uses int.Parse() for Integer type attributes and parses
    period-separated decimals for Double type. Rules:
    - "20.0" → "20"   (strip trailing zero + dot for integers)
    - "20.5" → "20.5" (preserve meaningful decimal)
    - "20"   → "20"   (passthrough)
    """
    if "." in value:
        f = float(value)
        if f == int(f):
            return str(int(f))
        return value  # preserve decimal
    return value
```

This helper replaces the inline logic in `write_data()`.

### Pattern 3: Auth Failure → ConfigEntryAuthFailed (BUGS-06)

Current `coordinator.py:_async_update_data` (lines 240-246):

```python
except VitotrolAuthError as err:
    _LOGGER.debug("Auth error (%s), re-logging in and retrying", err)
    try:
        await self.api.login()
        return await self._do_update()
    except VitotrolError as err:  # <-- catches VitotrolAuthError too (subclass)
        raise UpdateFailed(f"Re-auth failed: {err}") from err
```

The inner `except VitotrolError` swallows `VitotrolAuthError` from the retry, raising `UpdateFailed` instead of `ConfigEntryAuthFailed`. The fix:

```python
except VitotrolAuthError as err:
    _LOGGER.debug("Auth error (%s), re-logging in and retrying", err)
    try:
        await self.api.login()
        return await self._do_update()
    except VitotrolAuthError as retry_err:
        raise ConfigEntryAuthFailed(
            f"Credentials invalid: {retry_err}"
        ) from retry_err
    except VitotrolError as retry_err:
        raise UpdateFailed(f"Re-auth failed: {retry_err}") from retry_err
```

`ConfigEntryAuthFailed` must be imported: `from homeassistant.config_entries import ConfigEntryAuthFailed`

### Pattern 4: Empty Catalog Guard (BUGS-07)

Current `async_setup_type_info()` in coordinator.py has no guard for zero attrs. Add after fetching:

```python
catalog = await self.api.get_type_info(device)
if not catalog:
    _LOGGER.warning(
        "GetTypeInfo returned no attributes for device %s (id=%d) — skipping",
        device.device_name,
        device.device_id,
    )
    raise ConfigEntryNotReady(
        f"No attributes discovered for device {device.device_name!r}"
    )
```

### Pattern 5: Number Step Size from Metadata (BUGS-03)

`AttributeTypeInfo.type` is either `"Double"` or `"Integer"`. Current `number.py` ignores this and hardcodes `self._attr_native_step = 1.0`.

Decision: use `0.5` for temperature-type Double attrs, `1.0` otherwise.

```python
# In VitotrolNumber.__init__, replace the hardcoded step:
if info.type == "Double":
    # Temperature attributes typically allow 0.5-degree steps
    self._attr_native_step = 0.5
    self._attr_suggested_display_precision = 1
else:
    self._attr_native_step = 1.0
    self._attr_suggested_display_precision = 0
```

Also fix `native_value` return type — currently returns `int(float(raw))` which truncates decimals. For Double attrs:

```python
@property
def native_value(self) -> float | None:
    raw = self._get_attr_value(self._vitotrol_attr_id)
    if raw is None:
        return None
    try:
        v = float(raw)
        return v if self._info_type == "Double" else int(v)
    except (ValueError, OverflowError):
        ...
```

Store `self._info_type = info.type` at construction.

Also fix `async_set_native_value` — currently does `str(int(value))` unconditionally:

```python
async def async_set_native_value(self, value: float) -> None:
    # Use wire formatting consistent with api.py fix
    str_value = _format_wire_value(str(value))
    ...
```

### Pattern 6: Climate Preset Write Guard (BUGS-04)

`async_set_preset_mode` calls `async_write` on eco/party attrs without checking `writable`. The catalog is available via `coordinator.get_attribute_catalog(device_id)`. Add guard in `__init__` or as inline check:

```python
# Store writable flags at construction time (cleaner than re-fetching):
eco_writable = catalog.get(eco_attr, None)
self._eco_writable = eco_writable.writable if eco_writable else False
party_writable = ...

# Then in async_set_preset_mode:
if eco_attr is not None:
    eco_info = catalog.get(eco_attr)
    if eco_info and not eco_info.writable:
        _LOGGER.warning(
            "Climate %s: eco_mode attr %d is read-only — skipping write",
            self._device.device_name, eco_attr,
        )
    else:
        await self.coordinator.async_write(self._device, eco_attr, "1")
```

The catalog dict is passed to `VitotrolClimate.__init__` already — store it as `self._catalog` for later use.

### Pattern 7: Coordinator config_entry param (HAPAT-01)

Current `VitotrolCoordinator.__init__` signature:
```python
def __init__(self, hass, api, devices, scan_interval=300):
    super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=...)
```

Required change:
```python
from homeassistant.config_entries import ConfigEntry

def __init__(self, hass, api, devices, scan_interval=300, config_entry=None):
    super().__init__(
        hass, _LOGGER, name=DOMAIN,
        update_interval=timedelta(seconds=scan_interval),
        config_entry=config_entry,
    )
```

Call site in `__init__.py`:
```python
coordinator = VitotrolCoordinator(hass, api, devices, scan_interval, config_entry=entry)
```

### Pattern 8: Config Flow Strings Verification (HAPAT-02)

**Already done in strings.json** (verified by reading the file):
```json
"error": {
    "invalid_auth": "Invalid username or password.",
    "cannot_connect": "Unable to connect to the Vitotrol service.",
    "no_devices": "No devices found under this account."
}
```

Must verify `translations/en.json` contains the same — this file was not read during research. The pattern for HA translations is that `translations/en.json` mirrors `strings.json` exactly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reauth flow UI | Custom error page | `ConfigEntryAuthFailed` | HA handles the entire reauth UI flow automatically when this exception is raised from `_async_update_data` |
| User error notifications | Custom notification service | `HomeAssistantError` | HA shows this exception's message as an error toast in the UI automatically |
| Validation errors | Custom validator | `ServiceValidationError` | HA shows validation errors in a dedicated UI callout distinct from general errors |
| "Not ready" retries | Custom retry loop | `ConfigEntryNotReady` | HA automatically retries setup with backoff when this is raised from `async_setup_entry` |
| Step size detection | Custom schema parser | Read `AttributeTypeInfo.type` directly | The type is already parsed and available in the entity constructor |

## Common Pitfalls

### Pitfall 1: Swallowing VitotrolAuthError in Generic Except

**What goes wrong:** Inner `except VitotrolError` in `_async_update_data` catches `VitotrolAuthError` (subclass) and raises `UpdateFailed` instead of `ConfigEntryAuthFailed`. HA never prompts the user to re-authenticate.

**Why it happens:** Python exception hierarchy — `VitotrolAuthError` IS-A `VitotrolError`.

**How to avoid:** Always catch the specific subclass before the parent class; split the retry handler into `except VitotrolAuthError` and `except VitotrolError`.

**Warning signs:** Users report "polling failures" / integration going unavailable with no reauth prompt.

### Pitfall 2: Writing Decimal Values as Integers

**What goes wrong:** `api.py:write_data` converts `"20.5"` to `"20"` because `"." in value` triggers `str(int(float(value)))`. Server receives `"20"` for a temperature that should be `"20.5"`.

**Why it happens:** Incorrect assumption that all writable attributes are integers (true for most, not all).

**How to avoid:** Strip trailing `.0` only when `float(value) == int(float(value))`. Preserve the string as-is when it has meaningful decimal digits.

**Warning signs:** Temperature setpoints always round to nearest degree; device ignores sub-degree settings.

### Pitfall 3: Optimistic State Lingers After Write Failure

**What goes wrong:** If `async_write` raises before `_update_coordinator_data`, entity state stays at the pre-optimistic value until the next poll. If write raises after the optimistic update (impossible currently, but fragile), state lingers at wrong value.

**Why it happens:** Current code does optimistic update AFTER the write call — raising write exceptions means the update never runs. This is actually "correct" for the current (uncorrected) write failures, but the absence of `HomeAssistantError` means the user sees no error toast.

**How to avoid:** Capture old value before write. After any exception, explicitly call `_update_coordinator_data(attr_id, old_value)` to restore, then `async_write_ha_state()`.

**Warning signs:** HA UI shows device in a state different from the physical device after a failed write.

### Pitfall 4: Climate Preset Writing to Read-Only Attributes

**What goes wrong:** Some devices mark eco_mode/party_mode as read-only in GetTypeInfo. The climate preset code writes unconditionally, causing SOAP errors.

**Why it happens:** The preset attrs were assumed writable at development time. GetTypeInfo reveals the true capability per device.

**How to avoid:** Check `catalog[attr_id].writable` before any write. Log warning and skip if read-only.

**Warning signs:** Setting eco or party mode preset causes an error toast but only some attributes are changed (or none).

### Pitfall 5: Empty Catalog Creates Zero Entities Silently

**What goes wrong:** GetTypeInfo returns zero attributes (network error, unsupported device variant, or API change). Coordinator stores empty catalog; zero entities are created. Integration appears loaded but does nothing.

**Why it happens:** No guard currently exists in `async_setup_type_info()`.

**How to avoid:** Raise `ConfigEntryNotReady` when catalog has zero entries. HA will retry setup with backoff.

**Warning signs:** Integration loads without error, no entities appear in HA.

### Pitfall 6: DataUpdateCoordinator Without config_entry

**What goes wrong:** `DataUpdateCoordinator` without `config_entry` parameter cannot link the coordinator to the config entry properly — certain HA framework features (like automatic reauth handling and coordinator-based config entry state) may not work correctly.

**Why it happens:** `config_entry` is an optional parameter that was added to the HA coordinator framework — older code predates it.

**How to avoid:** Always pass `config_entry=config_entry` when constructing `DataUpdateCoordinator` in HA 2024+.

## Code Examples

### Test: Optimistic Rollback (covers TEST-02)

```python
# tests/test_switch.py addition:
async def test_turn_on_rolls_back_on_write_error(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """State reverts to old value when async_write raises an exception."""
    from homeassistant.exceptions import HomeAssistantError
    import pytest

    mock_api.return_value.get_type_info = AsyncMock(return_value={7855: FAKE_PARTY_MODE_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={7855: "0"})
    mock_api.return_value.write_data_wait = AsyncMock(
        side_effect=VitotrolError("connection refused")
    )

    await _load(hass, mock_config_entry)

    state_before = hass.states.get("switch.vitovalor_300_p_party_mode")
    assert state_before.state == "off"

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", "turn_on",
            {"entity_id": "switch.vitovalor_300_p_party_mode"},
            blocking=True,
        )

    # State must revert — not remain at optimistic "on"
    state_after = hass.states.get("switch.vitovalor_300_p_party_mode")
    assert state_after.state == "off"
```

### Test: Malformed Enum Values (covers TEST-03)

```python
# tests/test_coordinator.py or test_api.py addition:
async def test_get_type_info_malformed_enum_id_skipped(hass: HomeAssistant) -> None:
    """get_type_info skips enum entries with malformed IDs."""
    from custom_components.vitotrol.api import VitotrolAPI
    import aiohttp
    from unittest.mock import AsyncMock, patch

    # Build XML with a malformed enum sub-ID like "92-abc"
    xml = """<?xml version="1.0"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body>
        <GetTypeInfoResult>
          <Ergebnis>0</Ergebnis>
          <TypeInfoListe>
            <DatenpunktTypInfo>
              <DatenpunktId>92</DatenpunktId>
              <DatenpunktName>Betriebs_Art</DatenpunktName>
              <DatenpunktTyp>ENUM</DatenpunktTyp>
              ...
            </DatenpunktTypInfo>
            <DatenpunktTypInfo>
              <DatenpunktId>92-abc</DatenpunktId>  <!-- malformed -->
              <MinimalWert>Off</MinimalWert>
            </DatenpunktTypInfo>
          </TypeInfoListe>
        </GetTypeInfoResult>
      </soap:Body>
    </soap:Envelope>"""
    # Verify parser handles ValueError from int("abc") without crashing
    ...
```

### Test: Config Flow Empty Devices (covers TEST-04)

```python
# tests/test_config_flow.py addition (verify coverage):
async def test_config_flow_no_devices_shows_error(
    hass: HomeAssistant, mock_api
) -> None:
    """Config flow shows no_devices error when GetDevices returns empty list."""
    from homeassistant.data_entry_flow import FlowResultType

    mock_api.return_value.get_devices = AsyncMock(return_value=[])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "user@example.com", "password": "secret"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_devices"
```

### Test: Concurrent Writes (covers TEST-05)

```python
# tests/test_coordinator.py addition:
async def test_concurrent_writes_complete_independently(hass: HomeAssistant) -> None:
    """Two concurrent writes do not interfere with each other."""
    import asyncio

    api = AsyncMock()
    api.write_data_wait = AsyncMock(return_value=None)

    coord = _make_coordinator(hass, api)

    # Fire two writes concurrently
    await asyncio.gather(
        coord.async_write(FAKE_DEVICE, 7855, "1"),
        coord.async_write(FAKE_DEVICE, 7852, "1"),
    )

    assert api.write_data_wait.call_count == 2
    calls = {(c.args[1], c.args[2]) for c in api.write_data_wait.call_args_list}
    assert (7855, "1") in calls
    assert (7852, "1") in calls
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No `config_entry` in coordinator | Pass `config_entry=entry` to `DataUpdateCoordinator.__init__` | HA 2024.x | Coordinator properly linked to config entry for reauth and state management |
| Generic `UpdateFailed` on all errors | `ConfigEntryAuthFailed` for auth errors, `UpdateFailed` for others | HA 2022+ | HA automatically prompts reauth on `ConfigEntryAuthFailed` |
| No user error toasts from entities | `HomeAssistantError` from service calls | HA 2023+ | HA shows error messages directly in the UI notification area |
| Silent entity state on write failure | Raise + rollback | Best practice | Users know writes failed; UI stays consistent |

**Key HA version notes (verified against installed version in venv):**
- `ConfigEntryAuthFailed`: raises reauth flow automatically — import from `homeassistant.config_entries`
- `HomeAssistantError`: when raised from a service call handler (entity write method), HA 2024+ shows it as a red toast notification in the UI
- `ServiceValidationError`: shows as a yellow validation callout — use ONLY for user input validation (value out of range), NOT for API errors

## Open Questions

1. **translations/en.json content for `no_devices`**
   - What we know: `strings.json` has `no_devices` string
   - What's unclear: Whether `translations/en.json` has been updated to match
   - Recommendation: Read `translations/en.json` at plan time and add `no_devices` if missing

2. **BUGS-03: What does `type_value` encode vs `type`?**
   - What we know: `DatenpunktTyp` is `"Double"` or `"Integer"`; `DatenpunktTypWert` (stored as `type_value`) appears to be a numeric code
   - What's unclear: Whether `type_value` encodes precision (e.g., number of decimal places)
   - Recommendation: Use `type == "Double"` as the step indicator; default 0.5 for temperature Double attrs per user decision

3. **Malformed enum ID handling in `get_type_info`**
   - What we know: Current parser does `int(parts[1])` which raises `ValueError` on `"abc"`
   - What's unclear: Whether real API responses can produce malformed IDs
   - Recommendation: Add `try/except ValueError` around the enum index parse and skip malformed entries with a debug log

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with pytest-homeassistant-custom-component |
| Config file | `pytest.ini` (root) — `asyncio_mode = auto`, `testpaths = tests` |
| Quick run command | `.venv/bin/python -m pytest tests/ -x -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUGS-01 | Optimistic rollback on write failure | unit | `.venv/bin/python -m pytest tests/test_switch.py -k rollback -x` | ❌ Wave 0 |
| BUGS-02 | Value formatting strips .0 only for integers | unit | `.venv/bin/python -m pytest tests/test_api.py -k format -x` | ❌ Wave 0 |
| BUGS-03 | Number step size from metadata | unit | `.venv/bin/python -m pytest tests/test_number.py -k step -x` | ❌ Wave 0 |
| BUGS-04 | Climate preset skips read-only attrs | unit | `.venv/bin/python -m pytest tests/test_climate.py -k readonly -x` | ❌ Wave 0 |
| BUGS-05 | HomeAssistantError raised on write failure | unit | `.venv/bin/python -m pytest tests/ -k error -x` | ❌ Wave 0 |
| BUGS-06 | ConfigEntryAuthFailed on persistent auth error | unit | `.venv/bin/python -m pytest tests/test_coordinator.py -k auth_failed -x` | ❌ Wave 0 |
| BUGS-07 | ConfigEntryNotReady on empty catalog | unit | `.venv/bin/python -m pytest tests/test_coordinator.py -k empty_catalog -x` | ❌ Wave 0 |
| HAPAT-01 | Coordinator receives config_entry | unit | `.venv/bin/python -m pytest tests/test_coordinator.py -k config_entry -x` | ❌ Wave 0 |
| HAPAT-02 | Config flow shows no_devices error | unit | `.venv/bin/python -m pytest tests/test_config_flow.py -k no_devices -x` | check existing |
| TEST-02 | Optimistic rollback when WriteData raises | unit | `.venv/bin/python -m pytest tests/ -k rollback -x` | ❌ Wave 0 |
| TEST-03 | Malformed/empty enum values in GetTypeInfo | unit | `.venv/bin/python -m pytest tests/ -k malformed -x` | ❌ Wave 0 |
| TEST-04 | Config flow with empty device list | unit | `.venv/bin/python -m pytest tests/test_config_flow.py -k no_devices -x` | check existing |
| TEST-05 | Concurrent writes complete independently | unit | `.venv/bin/python -m pytest tests/test_coordinator.py -k concurrent -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/ -x -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New test functions in `tests/test_switch.py` — covers BUGS-01/TEST-02 rollback
- [ ] New test functions in `tests/test_climate.py` — covers BUGS-01/TEST-02 (multi-write rollback), BUGS-04
- [ ] New test functions in `tests/test_number.py` — covers BUGS-01/TEST-02, BUGS-03
- [ ] New test functions in `tests/test_select.py` — covers BUGS-01/TEST-02
- [ ] New test functions in `tests/test_coordinator.py` — covers BUGS-06, BUGS-07, HAPAT-01, TEST-05
- [ ] New test file or functions — covers BUGS-02 (`_format_wire_value` unit test)
- [ ] Verify/add test in `tests/test_config_flow.py` — covers HAPAT-02/TEST-04
- [ ] New test for malformed enum IDs — covers TEST-03 (may go in `tests/test_api.py`)

*(Existing test infrastructure covers the framework — only new test functions needed, no new files required for most)*

## Current Code State (Direct Inspection Findings)

### Files That Need Changes

| File | Change Required | Req IDs |
|------|----------------|---------|
| `coordinator.py` | Auth retry → `ConfigEntryAuthFailed`; empty catalog guard; add `config_entry` param | BUGS-06, BUGS-07, HAPAT-01 |
| `api.py` | Fix `_format_wire_value` in `write_data()` | BUGS-02 |
| `climate.py` | Wrap all 3 write methods with rollback+error; add preset write guard; store catalog | BUGS-01, BUGS-04, BUGS-05 |
| `switch.py` | Wrap `async_turn_on` and `async_turn_off` with rollback+error | BUGS-01, BUGS-05 |
| `number.py` | Wrap `async_set_native_value` with rollback+error; derive step from type | BUGS-01, BUGS-03, BUGS-05 |
| `select.py` | Wrap `async_select_option` with rollback+error | BUGS-01, BUGS-05 |
| `__init__.py` | Pass `config_entry=entry` to coordinator constructor | HAPAT-01 |
| `translations/en.json` | Verify `no_devices` string present | HAPAT-02 |

### Already Correct (No Changes Needed)

- `strings.json` — `no_devices` error string already present (verified)
- `config_flow.py` — Three distinct error keys correctly set
- `api.py` — SOAP field names, namespace, auth error detection correct
- `entity.py` — `_get_attr_value`, `_update_coordinator_data` helpers work correctly for rollback pattern

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `coordinator.py`, `entity.py`, `climate.py`, `switch.py`, `number.py`, `select.py`, `api.py`, `config_flow.py`, `strings.json`, `attributes.py`
- `tests/conftest.py`, `tests/test_coordinator.py`, `tests/test_number.py`, `tests/test_climate.py` — confirmed test patterns and existing coverage
- `pytest.ini` — confirmed test runner config
- Venv: 112 tests pass with `.venv/bin/python -m pytest tests/ -q`

### Secondary (MEDIUM confidence)
- HA exception behavior (`HomeAssistantError` → toast, `ConfigEntryAuthFailed` → reauth flow) — inferred from code patterns and HA documentation conventions; not fetched from live docs

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already in use; venv verified working
- Architecture: HIGH — all fixes derived from direct code reading
- Pitfalls: HIGH — all identified by reading the actual bugs in source
- Test patterns: HIGH — existing test files read; patterns are consistent and clear

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (stable HA integration patterns)
