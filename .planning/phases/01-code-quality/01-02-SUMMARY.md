---
phase: 01-code-quality
plan: "02"
subsystem: api
tags: [soap, write-data, value-formatting, bug-fix, tdd]

# Dependency graph
requires:
  - phase: 01-code-quality
    provides: api.py SOAP client with write_data method
provides:
  - _format_wire_value helper in api.py that correctly strips .0 only for whole numbers
  - write_data uses _format_wire_value instead of truncating all decimal values
affects: [number.py, climate.py, any entity that calls write_data_wait]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Module-level helper for value formatting before SOAP serialization"]

key-files:
  created:
    - tests/test_api.py
  modified:
    - custom_components/vitotrol/api.py

key-decisions:
  - "Preserve original value string for non-whole-number floats — do not convert via float() which could introduce precision artifacts"
  - "OverflowError caught alongside ValueError in case of extremely large numeric strings"

patterns-established:
  - "TDD: write failing tests first, then implement, as specified in plan"
  - "Module-level helpers at bottom of api.py under Module-level helpers section"

requirements-completed: [BUGS-02]

# Metrics
duration: 4min
completed: 2026-03-04
---

# Phase 1 Plan 02: WriteData Value Formatting Fix Summary

**Fixed data-loss bug where temperature setpoints with 0.5-degree precision (e.g. "20.5") were silently truncated to integers on every write; added _format_wire_value helper that strips .0 only for whole numbers**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-04T19:00:00Z
- **Completed:** 2026-03-04T19:01:25Z
- **Tasks:** 1 (TDD: 2 commits — test then implementation)
- **Files modified:** 2

## Accomplishments

- Added `_format_wire_value` module-level helper to `api.py` with correct decimal-stripping logic
- Fixed `write_data` to use `_format_wire_value` instead of inline `str(int(float(value)))` truncation
- Created `tests/test_api.py` with 6 parameterized test cases covering all edge cases

## Task Commits

Each task was committed atomically (TDD split into two commits):

1. **Task 1 RED: Failing tests** - `3d4d1bd` (test)
2. **Task 1 GREEN: Implementation** - `dc0bfd7` (feat)

## Files Created/Modified

- `tests/test_api.py` - New test file with 6 tests for `_format_wire_value`
- `custom_components/vitotrol/api.py` - Added `_format_wire_value` helper; replaced inline truncation in `write_data`

## Decisions Made

- Preserved original value string for non-whole-number floats: the helper returns the original `value` string (not `str(f)`) for fractional floats, avoiding any float-to-string precision artifacts
- Caught `OverflowError` alongside `ValueError` for defensive correctness on extreme inputs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Write operations now correctly transmit decimal setpoints (e.g. 20.5 degrees)
- Existing integer-only attributes continue to work (whole-number floats stripped of .0)
- Ready to proceed with Plan 03 (remaining code quality tasks)

---
*Phase: 01-code-quality*
*Completed: 2026-03-04*
