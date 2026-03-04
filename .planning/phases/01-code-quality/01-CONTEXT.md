# Phase 1: Code Quality - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix write operation bugs, HA error patterns, and test coverage. Scope: everything needed for write operations to be correct, error-transparent, and tested. CI, release pipeline, and HACS publishing are Phase 2.

</domain>

<decisions>
## Implementation Decisions

### Optimistic state rollback (BUGS-01)
- When `coordinator.async_write()` raises any exception, entity state must revert to the last actual device value (the value in coordinator data before the optimistic update)
- Do NOT leave state in limbo until next poll — immediately revert on exception
- No immediate coordinator refresh on failure — let the next scheduled poll restore truth

### WriteData value formatting (BUGS-02)
- Strip trailing `.0` for integers: `"20.0"` → `"20"`; preserve decimals: `"20.5"` → `"20.5"`
- Use period as decimal separator (confirmed from WSDL — commas cause FormatException)
- Fix applies wherever values are sent via `api.write_data_wait()`

### Number entity step size (BUGS-03)
- Step size must be derived from `GetTypeInfo` metadata (`DatenpunktTyp` and step/precision info), not hardcoded `1.0`
- If GetTypeInfo provides no precision, default to `1.0` (integers) or `0.5` (temperatures — Claude's discretion)

### Climate preset write guard (BUGS-04)
- Before writing eco_mode or party_mode attrs, check `writable` flag from attribute catalog
- If attr is read-only: log a warning and skip that write — do NOT raise an error to the user
- Writable attrs in the same preset still apply normally

### Write error surfacing (BUGS-05)
- All entity write methods (climate, switch, number, select) must wrap `coordinator.async_write()` in try/except
- On failure: raise `HomeAssistantError` — this produces a user-visible error toast in HA
- Use `ServiceValidationError` only for user input validation failures (e.g., value out of range) — not for API/network failures
- Error message should be descriptive: include attr name and the exception message

### Auth failure in coordinator (BUGS-06)
- When `_async_update_data` encounters `VitotrolAuthError` and the re-auth retry ALSO fails with `VitotrolAuthError`, raise `ConfigEntryAuthFailed` (not `UpdateFailed`)
- This triggers HA's built-in reauth flow (prompts user to re-enter credentials)
- Non-auth errors after retry remain `UpdateFailed`

### Empty GetTypeInfo catalog (BUGS-07)
- If `GetTypeInfo` returns zero attributes for a device: log a warning with device ID
- Raise `ConfigEntryNotReady` (not silent zero-entity creation)

### Coordinator constructor (HAPAT-01)
- Add `config_entry: ConfigEntry` parameter to `VitotrolCoordinator.__init__`
- Pass it to `DataUpdateCoordinator.__init__` as `config_entry=config_entry`
- Required for HA to link the coordinator to the config entry (standard HA pattern)

### Config flow error messages (HAPAT-02)
- Three distinct `errors["base"]` keys already in code: `invalid_auth`, `cannot_connect`, `no_devices`
- Verify matching strings exist in `strings.json` and `translations/en.json` with user-friendly messages:
  - `invalid_auth`: "Invalid username or password"
  - `cannot_connect`: "Cannot connect to Vitotrol service"
  - `no_devices`: "No devices found for this account"
- If `no_devices` string is missing, add it

### Claude's Discretion
- Exact error message wording for `HomeAssistantError` (be descriptive, format is flexible)
- Step size default for temperature attrs if GetTypeInfo doesn't specify precision
- Internal refactor approach for wrapping write methods (helper vs inline try/except)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `coordinator.async_write()`: already handles re-auth retry; entities call it directly — add try/except at call sites
- `_update_coordinator_data()` in `VitotrolEntity`: updates coordinator dict in-place; call with original value to roll back
- `_get_attr_value()` in `VitotrolEntity`: reads current value from coordinator data — capture before optimistic write for rollback
- Attribute catalog from `get_attribute_catalog()`: has `IstSchreibbar` flag — use this for preset write guard

### Established Patterns
- All entities inherit `VitotrolEntity(CoordinatorEntity)` — write fix applies consistently across all 5 platforms
- Write methods follow the pattern: `await coordinator.async_write(device, attr_id, value)` → `_update_coordinator_data(attr_id, value)` → `async_write_ha_state()`
- The optimistic update (`_update_coordinator_data`) currently happens AFTER `async_write` — so if `async_write` raises, no optimistic state is set. The rollback fix is: capture pre-write value, write, if exception → restore pre-write value in coordinator data and re-raise as `HomeAssistantError`

### Integration Points
- `coordinator.py:VitotrolCoordinator.__init__` — add `config_entry` param
- `coordinator.py:_async_update_data` — change auth retry path to raise `ConfigEntryAuthFailed`
- `coordinator.py:async_setup_type_info` — add empty catalog guard (raise `ConfigEntryNotReady`)
- `climate.py`, `switch.py`, `number.py`, `select.py` — wrap `async_write` calls in try/except
- `number.py` — derive step from attribute catalog metadata
- `strings.json` + `translations/en.json` — verify/add `no_devices` error string

</code_context>

<specifics>
## Specific Ideas

- No specific UX references given — implement to standard HA patterns
- Error toasts: HA shows `HomeAssistantError` messages directly in the UI notification area
- The rollback approach: capture `old_value = self._get_attr_value(attr_id)` before write, restore on exception

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-code-quality*
*Context gathered: 2026-03-04*
