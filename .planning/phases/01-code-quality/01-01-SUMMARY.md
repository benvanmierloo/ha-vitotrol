---
phase: 01-code-quality
plan: "01"
subsystem: coordinator
tags: [home-assistant, coordinator, config-entry, auth, error-handling]

# Dependency graph
requires: []
provides:
  - VitotrolCoordinator linked to config entry via config_entry param
  - ConfigEntryAuthFailed raised on persistent credential failure (triggers HA reauth flow)
  - ConfigEntryNotReady raised when GetTypeInfo returns zero attributes (visible failure)
affects: [02-02, 02-03, 02-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ConfigEntryAuthFailed: raised on persistent VitotrolAuthError in retry path"
    - "ConfigEntryNotReady: raised from coordinator setup when device returns no attributes"
    - "config_entry kwarg: pass entry to DataUpdateCoordinator super().__init__ for HA linkage"

key-files:
  created: []
  modified:
    - custom_components/vitotrol/coordinator.py
    - custom_components/vitotrol/__init__.py

key-decisions:
  - "Split inner except in auth retry: VitotrolAuthError -> ConfigEntryAuthFailed, VitotrolError -> UpdateFailed"
  - "Empty catalog guard placed before catalog assignment, raises ConfigEntryNotReady with device name"
  - "ConfigEntryNotReady from async_setup_type_info propagates through __init__.py naturally (not a VitotrolError subclass)"

patterns-established:
  - "TDD: write failing tests, commit, implement, verify green, commit"

requirements-completed: [HAPAT-01, BUGS-06, BUGS-07]

# Metrics
duration: 2min
completed: 2026-03-04
---

# Phase 1 Plan 01: Coordinator HA Framework Correctness Summary

**ConfigEntryAuthFailed on persistent auth error, ConfigEntryNotReady on empty catalog, and config_entry linkage added to VitotrolCoordinator**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-04T18:56:43Z
- **Completed:** 2026-03-04T18:58:45Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- VitotrolCoordinator now accepts `config_entry` kwarg and passes it to `DataUpdateCoordinator.__init__`, properly linking coordinator to its config entry
- Persistent `VitotrolAuthError` on retry now raises `ConfigEntryAuthFailed` (not `UpdateFailed`), enabling HA's reauth flow when credentials become invalid
- `async_setup_type_info` raises `ConfigEntryNotReady` with a warning log when `GetTypeInfo` returns zero attributes, preventing silent empty-entity setups

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `a729da2` (test)
2. **Task 1 GREEN: config_entry param + ConfigEntryAuthFailed** - `ed29309` (feat)
3. **Task 2 GREEN: Empty catalog guard** - `1370f39` (feat)
4. **Task 3: Pass config_entry at call site** - `9b9e87f` (feat)

_Note: Tasks 1 and 2 used TDD. The RED commit covers both task 1 and task 2 tests together. Tasks were implemented separately in two GREEN commits._

## Files Created/Modified

- `custom_components/vitotrol/coordinator.py` - Added imports (ConfigEntry, ConfigEntryAuthFailed, ConfigEntryNotReady), config_entry kwarg to __init__, split auth retry, empty catalog guard
- `custom_components/vitotrol/__init__.py` - Added config_entry=entry to VitotrolCoordinator constructor call

## Decisions Made

- Split the inner `except VitotrolError` in the auth retry path into two branches: `VitotrolAuthError -> ConfigEntryAuthFailed` and `VitotrolError -> UpdateFailed`. This is the correct HA pattern — persistent bad credentials should trigger reauth, not just mark the coordinator unavailable.
- Empty catalog guard is placed before `self._attribute_catalog[device.device_id] = catalog` to fail fast and leave the catalog in a clean state.
- `ConfigEntryNotReady` from `async_setup_type_info` propagates through `__init__.py`'s `except VitotrolError` guard naturally because `ConfigEntryNotReady` is not a `VitotrolError` subclass.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Coordinator now properly integrated with HA's config entry machinery
- Reauth flow will trigger when credentials expire (visible to user)
- Empty device catalogs surface as visible failures with backoff retry
- Ready for plans 01-02 through 01-04

---
*Phase: 01-code-quality*
*Completed: 2026-03-04*

## Self-Check: PASSED

- coordinator.py: FOUND
- __init__.py: FOUND
- 01-01-SUMMARY.md: FOUND
- Commits a729da2, ed29309, 1370f39, 9b9e87f: ALL FOUND
- 117 tests passing
