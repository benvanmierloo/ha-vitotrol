# Roadmap: Vitotrol HASS — Ship to HACS

## Overview

The integration is functionally complete but has known bugs in write handling, missing HA error patterns, no CI pipeline, and no HACS publishing metadata. The roadmap delivers a trustworthy v1.0.0 HACS release in two phases: fix code quality issues that would generate immediate user complaints, then establish CI/release automation and complete the remaining HACS polish (logo, README check) for publication.

## Phases

**Phase Numbering:**
- Integer phases (1, 2): Planned milestone work
- Decimal phases (1.1, 1.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Code Quality** - Fix write handling bugs, HA error patterns, and cover them with tests
- [ ] **Phase 2: CI, Release, and Publish** - Automated pytest CI, release workflow, version bump, brand logo, README check

## Phase Details

### Phase 1: Code Quality
**Goal**: Integration handles all write operations correctly with proper error feedback, triggers reauth on credential expiry, and guards against invalid writes — all validated by tests
**Depends on**: Nothing (first phase)
**Requirements**: BUGS-01, BUGS-02, BUGS-03, BUGS-04, BUGS-05, BUGS-06, BUGS-07, HAPAT-01, HAPAT-02, TEST-02, TEST-03, TEST-04, TEST-05
**Success Criteria** (what must be TRUE):
  1. User sees an error toast in HA when a write operation (climate setpoint, switch toggle, number change, select change) fails or times out — entity state reverts to actual device value
  2. User is prompted to re-authenticate via HA's reauth flow when stored credentials become invalid, rather than seeing silent polling failures
  3. User setting a climate preset that includes a read-only attribute sees a warning log but no crash — writable attributes in the preset still apply
  4. Number entity step sizes match the device's actual precision (from GetTypeInfo metadata), and decimal values like 20.5 are written correctly without SOAP FormatException
  5. All new error-handling paths have pytest coverage (optimistic rollback, malformed enums, empty device list, concurrent writes)
**Plans**: 4 plans

Plans:
- [ ] 01-01-PLAN.md — Coordinator: config_entry param, ConfigEntryAuthFailed, empty catalog guard
- [ ] 01-02-PLAN.md — API: fix WriteData value formatting (_format_wire_value)
- [ ] 01-03-PLAN.md — Entity platforms: rollback + HomeAssistantError + preset write guard + number step size
- [ ] 01-04-PLAN.md — Tests: rollback, malformed enums, empty device list, concurrent writes

### Phase 2: CI, Release, and Publish
**Goal**: Every push and PR is validated by automated tests, tagging a version creates a GitHub Release, and the repository has all brand assets and README polish needed for HACS users to discover and install
**Depends on**: Phase 1
**Requirements**: TEST-01, REL-01, REL-02, REL-03, HACS-01, HACS-03
**Success Criteria** (what must be TRUE):
  1. Pushing a commit or opening a PR triggers a GitHub Actions pytest workflow that reports pass/fail with a badge in the README
  2. Pushing a `v*` tag automatically creates a GitHub Release with the tag name and changelog
  3. `manifest.json` version is set to `1.0.0` and hassfest validation passes in CI
  4. Repository has `brand/logo.png` and `brand/logo@2x.png` (landscape Viessmann/Vitotrol mark, no HA branding) served directly from the repo
  5. README includes HACS install badge, step-by-step install instructions, supported entity platforms, and known limitations (single session, 10-15s refresh cycle)
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Code Quality | 2/4 | In Progress|  |
| 2. CI, Release, and Publish | 0/? | Not started | - |
