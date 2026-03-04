---
phase: 01-code-quality
plan: "03"
subsystem: entity-platforms
tags: [home-assistant, write-operations, error-handling, rollback, optimistic-updates]

# Dependency graph
requires:
  - phase: 01-code-quality-01
    provides: coordinator.async_write, VitotrolEntity helpers (_get_attr_value, _update_coordinator_data)
  - phase: 01-code-quality-02
    provides: api._format_wire_value (correct wire-safe value formatting)
provides:
  - Optimistic rollback pattern in switch.py, number.py, select.py, climate.py
  - HomeAssistantError raised on write failure (user-visible error toast in HA UI)
  - Number entity step size from GetTypeInfo metadata (0.5 for Double, 1.0 for Integer)
  - Number entity returns float/int native_value correctly (no int-truncation of Double)
  - Climate preset write guard: read-only eco_mode/party_mode attrs skipped with warning log
affects: [entity-platforms, write-operations, user-feedback]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optimistic rollback: capture old value before write, restore on exception, raise HomeAssistantError"
    - "TDD: RED (failing test commit) → GREEN (implementation commit) per task"
    - "Climate preset writable guard: check catalog.writable before eco/party writes, skip RO with warning"
    - "Number type-aware formatting: Double -> str(float), Integer -> str(int)"

key-files:
  created: []
  modified:
    - custom_components/vitotrol/switch.py
    - custom_components/vitotrol/number.py
    - custom_components/vitotrol/select.py
    - custom_components/vitotrol/climate.py
    - tests/test_switch.py
    - tests/test_number.py
    - tests/test_select.py
    - tests/test_climate.py

key-decisions:
  - "Rollback uses _update_coordinator_data to restore old value in coordinator.data directly — state reverts immediately without a poll cycle"
  - "Number.native_value returns float for Double type and int for Integer type — coordinator stores raw strings, entities parse to native types"
  - "Climate preset writable guard: skip read-only attrs silently (warning log) rather than raising; partial presets (eco skipped) are valid UX"
  - "Test for Double write: number.py passes '55.0' to coordinator, api.py _format_wire_value strips '.0' internally — test updated to '55.0'"

patterns-established:
  - "Write guard pattern: old = get(); try: write(); update(new); write_state() except: update(old); write_state(); raise HomeAssistantError"
  - "Preset multi-attr rollback: capture ALL attrs before try block; restore ALL in except block"

requirements-completed:
  - BUGS-01
  - BUGS-03
  - BUGS-04
  - BUGS-05

# Metrics
duration: 25min
completed: 2026-03-04
---

# Phase 1 Plan 03: Entity Write Rollback + Error Surfacing Summary

**Optimistic-rollback + HomeAssistantError pattern applied to switch, number, select, and climate write operations; number step size from GetTypeInfo type metadata; climate preset guard for read-only eco/party attrs**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-04T19:10:00Z
- **Completed:** 2026-03-04T19:35:00Z
- **Tasks:** 3 (TDD: 6 commits)
- **Files modified:** 8

## Accomplishments

- All four write platforms (switch, number, select, climate) now raise HomeAssistantError on write failure — user sees error toast in HA UI
- All write methods capture old coordinator data before writing and restore it on exception (state reverts immediately)
- Number entity step size set from GetTypeInfo attribute type: Double=0.5, Integer=1.0
- Number entity native_value returns float for Double-type attrs (not int-truncated) and int for Integer-type
- Climate preset mode changes check catalog.writable flag; read-only eco_mode/party_mode attrs are skipped with warning log rather than crashing
- 135 tests pass (12 new tests added via TDD)

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: switch.py rollback + HomeAssistantError**
   - `6da5c22` test(01-03): add failing RED tests for switch rollback
   - `e29d420` feat(01-03): add rollback + HomeAssistantError to switch.py

2. **Task 2: number.py step size, decimal value, rollback + HomeAssistantError**
   - `84253d5` test(01-03): add failing RED tests for number step/decimal/rollback
   - `23e4785` feat(01-03): fix number.py — step size, decimal value, rollback + HomeAssistantError

3. **Task 3: select.py + climate.py rollback + preset guard**
   - `09b17b7` test(01-03): add failing RED tests for select/climate rollback + readonly guard
   - `9ae6f81` feat(01-03): add rollback + HomeAssistantError to select.py and climate.py

## Files Created/Modified

- `custom_components/vitotrol/switch.py` — HomeAssistantError import; async_turn_on/off with rollback
- `custom_components/vitotrol/number.py` — HomeAssistantError import; _info_type storage; step size from type; float/int native_value; rollback in async_set_native_value
- `custom_components/vitotrol/select.py` — HomeAssistantError import; rollback in async_select_option
- `custom_components/vitotrol/climate.py` — HomeAssistantError import; rollback in async_set_temperature, async_set_hvac_mode; preset guard + multi-attr rollback in async_set_preset_mode
- `tests/test_switch.py` — 2 new rollback tests
- `tests/test_number.py` — 6 new tests (step size, decimal value, rollback) + 2 updated tests
- `tests/test_select.py` — 1 new rollback test
- `tests/test_climate.py` — 4 new tests (temperature/hvac/preset rollback + readonly preset guard)

## Decisions Made

- Rollback via `_update_coordinator_data(attr_id, old_value)` followed by `async_write_ha_state()` restores state in the current poll cycle without waiting for the next coordinator refresh.
- Number type-aware write: `str(float)` for Double (e.g., `"55.0"`), `str(int)` for Integer (e.g., `"55"`). The api.py `_format_wire_value` helper strips `.0` for whole-number floats before the SOAP call — the number entity does not need to replicate this logic.
- Climate preset writable guard: failing silently (warning log) rather than raising is correct UX — a device that reports eco_mode as read-only in GetTypeInfo simply doesn't support it; the preset write still succeeds for whichever attrs are writable.
- Existing test `test_set_value_writes_integer` updated to `test_set_value_writes_double` with expected value `"55.0"` — the old test was testing the broken int-truncation behavior.
- Existing test `test_hot_water_setpoint_value` updated to expect state `"55.0"` — the attr is Double type so float value is correct.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated two existing number tests that tested wrong (broken) behavior**
- **Found during:** Task 2 (number.py implementation)
- **Issue:** `test_set_value_writes_integer` expected `"55"` from a Double-type attr — this was testing the int-truncation bug we were fixing. `test_hot_water_setpoint_value` expected state `"55"` instead of `"55.0"`.
- **Fix:** Updated both tests to match the correct new behavior.
- **Files modified:** tests/test_number.py
- **Verification:** All 10 number tests pass after the fix.
- **Committed in:** `23e4785` (Task 2 feat commit)

**2. [Rule 1 - Bug] Integer-type test used attr_id=82 (platform="none") — corrected to attr_id=85**
- **Found during:** Task 2 (running new number tests)
- **Issue:** FAKE_INTEGER_SETPOINT_INFO used attr_id=82 which is platform="none" in ATTRIBUTE_REGISTRY (used by climate, not number). The entity was never created so the test asserted None.
- **Fix:** Switched to attr_id=85 (Reduced temperature setpoint, platform="num_temp", enabled=True).
- **Files modified:** tests/test_number.py
- **Verification:** `test_integer_attr_has_step_1_0` and `test_integer_native_value_returns_int` pass.
- **Committed in:** `23e4785` (Task 2 feat commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - correcting tests that tested broken behavior)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep; production code matches plan exactly.

## Issues Encountered

None — implementation matched plan specifications exactly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All four write platforms now raise HomeAssistantError on failure with state rollback
- Phase 1 plan 3 of 4 complete — next: plan 04 (if any)
- BUGS-01, BUGS-03, BUGS-04, BUGS-05 requirements fulfilled

## Self-Check: PASSED

All files confirmed present. All task commits verified in git log.

---
*Phase: 01-code-quality*
*Completed: 2026-03-04*
