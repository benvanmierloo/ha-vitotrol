# Requirements: Vitotrol HASS

**Defined:** 2026-03-04
**Core Value:** Users with Viessmann boilers can monitor and control their heating system natively in Home Assistant, with automatic attribute discovery and no manual datapoint configuration.

## v1 Requirements

Requirements for the v1.0.0 HACS release. Each maps to roadmap phases.

### Bug Fixes

- [x] **BUGS-01**: Integration reverts entity state to actual device value when WriteData fails or times out (no indefinite stale optimistic state)
- [x] **BUGS-02**: WriteData value formatted correctly — strip `.0` suffix for integers (`"20.0"` → `"20"`), preserve decimals (`"20.5"` → `"20.5"`); no SOAP FormatException
- [x] **BUGS-03**: Number entity step size derived from GetTypeInfo metadata instead of hardcoded `1.0`
- [x] **BUGS-04**: Climate preset writes check `writable` flag before attempting write to eco_mode/party_mode attributes; read-only attributes skipped with warning log
- [x] **BUGS-05**: All entity write operations (climate, switch, number, select) raise `HomeAssistantError` or `ServiceValidationError` on failure, producing user-visible HA error toasts
- [x] **BUGS-06**: Authentication failures in coordinator polling raise `ConfigEntryAuthFailed`, triggering HA's built-in reauth flow
- [x] **BUGS-07**: Empty GetTypeInfo catalog (zero attributes returned) logs a warning and raises `ConfigEntryNotReady` rather than silently creating zero entities

### HA Patterns

- [x] **HAPAT-01**: `VitotrolCoordinator` receives `config_entry` as constructor parameter and passes it to `DataUpdateCoordinator.__init__`
- [ ] **HAPAT-02**: Config flow surfaces distinct error messages for auth failure, network error, and no-devices-found cases

### Test Coverage

- [ ] **TEST-01**: Pytest GitHub Actions workflow runs on push, pull_request, and weekly schedule; badge shown in README
- [ ] **TEST-02**: Test covers optimistic state rollback when WriteData raises exception
- [ ] **TEST-03**: Test covers GetTypeInfo response with malformed/empty enum values
- [ ] **TEST-04**: Test covers config flow behavior when GetDevices returns empty device list
- [ ] **TEST-05**: Test covers concurrent write operations completing independently

### Release Pipeline

- [ ] **REL-01**: GitHub Actions release workflow auto-creates GitHub Release when a `v*` tag is pushed
- [ ] **REL-02**: `manifest.json` version set to `1.0.0`
- [ ] **REL-03**: First GitHub Release `v1.0.0` published with changelog

### HACS Submission

- [ ] **HACS-01**: `brand/logo.png` and `brand/logo@2x.png` created (landscape Viessmann/Vitotrol, no HA branding)
- [ ] **HACS-03**: README quality check — verify HACS install badge, install instructions, supported platforms, and known limitations are present and accurate

## v1.x Requirements

Scoped for a point release after v1.0.0 has been stable for 2-4 weeks.

### Enhancements

- **ENH-01**: HA service `vitotrol.refresh_data` triggers an immediate out-of-cycle coordinator refresh for a device
- **ENH-02**: Device registry entry populated with manufacturer, model, and firmware version sourced from the Viessmann API (requires investigation of what GetDevices/GetTypeInfo actually returns)

## Already Complete / Not Needed

| Requirement | Original ID | Status | Notes |
|-------------|-------------|--------|-------|
| GitHub repository description and topics set | HACS-02 | Done | Repo already has description and topics |
| PR submitted to `hacs/default` repository | HACS-04 | Done | PR already submitted |
| PR submitted to `home-assistant/brands` | HACS-05 | Not needed | HA 2026.3 serves brand assets from the repo's `brand/` directory directly |

## Out of Scope

| Feature | Reason |
|---------|--------|
| German translations | v2 — English sufficient for v1 global release |
| Concurrent session handling | API limitation — Viessmann allows one session per account |
| Entity grouping by heating circuit | HA UI concern — users can group via dashboards |
| Session timeout enforcement (24h re-login) | Low priority — re-auth on error is sufficient |
| Local/LAN API | No local API known to exist for Vitotrol systems |
| Mobile app | Web/HA only |
| Value history / trend analysis | Handled by HA built-in history |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUGS-01 | Phase 1 | Complete |
| BUGS-02 | Phase 1 | Complete |
| BUGS-03 | Phase 1 | Complete |
| BUGS-04 | Phase 1 | Complete |
| BUGS-05 | Phase 1 | Complete |
| BUGS-06 | Phase 1 | Complete |
| BUGS-07 | Phase 1 | Complete |
| HAPAT-01 | Phase 1 | Complete |
| HAPAT-02 | Phase 1 | Pending |
| TEST-01 | Phase 2 | Pending |
| TEST-02 | Phase 1 | Pending |
| TEST-03 | Phase 1 | Pending |
| TEST-04 | Phase 1 | Pending |
| TEST-05 | Phase 1 | Pending |
| REL-01 | Phase 2 | Pending |
| REL-02 | Phase 2 | Pending |
| REL-03 | Phase 2 | Pending |
| HACS-01 | Phase 2 | Pending |
| HACS-03 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0
- Already complete / not needed: 3 (HACS-02, HACS-04, HACS-05)

---
*Requirements defined: 2026-03-04*
*Last updated: 2026-03-04 after roadmap revision*
