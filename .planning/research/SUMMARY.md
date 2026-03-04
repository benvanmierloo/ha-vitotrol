# Project Research Summary

**Project:** Vitotrol HASS — Ship to HACS
**Domain:** Home Assistant custom integration (HACS publishing pipeline)
**Researched:** 2026-03-04
**Confidence:** HIGH

## Executive Summary

This project is a functioning Home Assistant custom integration for Viessmann Vitotrol heating systems that is nearly ready to ship to HACS, but has a defined set of code quality gaps, bug fixes, and publishing tasks blocking v1.0.0. The integration already has working entity platforms, config flow, coordinator, SOAP API client, diagnostics, and a test suite. What it lacks is: correct HA error-handling patterns (action exceptions, ConfigEntryAuthFailed, RO guards), a CI pytest workflow, a release pipeline, and several HACS repository metadata items.

The recommended approach is a three-phase delivery: fix the known code quality bugs that would erode user trust (bad write error handling, optimistic state without proper failure paths, decimal formatting), set up the CI and release pipeline that HACS requires, and then handle the remaining pre-release checklist (repository metadata, brand assets, README quality, HACS default submission). This order is deliberate — shipping broken write behavior to HACS would generate bug reports immediately, and setting up CI before creating releases prevents bad versions from reaching users.

The key risk is entity unique ID stability. Any change to `entity_key_for_attr()` or `AttrMeta.name` values after v1.0.0 ships will orphan user automations and history, which is unrecoverable without migration code. Lock down the unique ID contract before the first release and treat it as immutable from that point forward.

## Key Findings

### Recommended Stack

The integration's existing stack is correct and complete for HACS submission. `manifest.json` has all 6 required fields, `hacs.json` is valid, `defusedxml>=0.7.1` is the only PyPI dependency, and brand assets (`icon.png`, `icon@2x.png`) are already present. No stack changes are needed for the integration itself.

The publishing pipeline has specific gaps: no GitHub Releases exist (HACS requires full release objects, not just git tags), CI workflows are missing `workflow_dispatch` and `schedule` triggers, no `logo.png` brand asset exists, and no release automation workflow exists. The `homeassistant` minimum version in `hacs.json` should be updated from `2024.12.0` to `2025.1.0` when shipping.

**Core technologies:**
- `defusedxml>=0.7.1`: SOAP XML parsing — only external dependency, already bundled by HA
- `aiohttp.ClientSession`: HTTP transport — shared HA session, no custom client needed
- `DataUpdateCoordinator`: polling orchestration — standard HA pattern, correctly implemented
- GitHub Actions (`hacs/action@main`, `home-assistant/actions/hassfest@master`): CI validation — already configured, needs trigger additions

### Expected Features

The integration already has all working-code features. What constitutes v1 table stakes is now the combination of bug fixes and publishing infrastructure.

**Must have (table stakes — v1 blockers):**
- Optimistic state with proper failure handling — users see wrong state for 300s when writes fail; unacceptable for climate/heating
- WriteData decimal formatting fix — `"20.0"` causes `FormatException` on the SOAP API; documented in MEMORY.md
- Number entity step from GetTypeInfo metadata — hardcoded step=1.0 breaks decimal-valued attributes
- Climate preset RO/RW guard — writing to read-only eco/party attributes fails silently; known bug
- Action exceptions (HomeAssistantError / ServiceValidationError) — raw exceptions propagate; no user-visible error feedback
- ConfigEntryAuthFailed — auth errors currently treated same as network errors; no reauth prompt triggered
- CI pytest workflow — tests exist but no CI runs them; badges matter to users and reviewers
- GitHub Releases with version tags — HACS cannot display or track versions without release objects
- Empty GetTypeInfo catalog warning — zero entities created with no error is confusing
- GitHub repo description and topics — required for HACS default inclusion

**Should have (v1.x differentiators):**
- Release automation workflow (tag-triggered GitHub Release creation)
- GitHub issue/bug report templates
- HACS default repository submission (PR to hacs/default after v1 stabilizes 2-4 weeks)
- German translations (significant user base in DACH market)
- Manual refresh service (`vitotrol.refresh_data`)
- Device info enrichment from API (model/firmware in device registry)
- Diagnostics attribute catalog dump

**Defer (v2+):**
- Session timeout enforcement (24h forced re-login)
- Disabled entity pruning from poll set (optimization, low priority)
- Dynamic preset/option refresh on catalog change (firmware updates are rare)
- Concurrent session handling (API limitation, not fixable in integration)

### Architecture Approach

The integration's five-layer architecture is sound and should not be restructured. The required changes are targeted improvements within existing layers: raise `ConfigEntryAuthFailed` instead of `UpdateFailed` for auth errors in coordinator and setup, wrap all entity write methods in try/except raising `HomeAssistantError` on failure, move optimistic state updates to after the write await (not before), add RO guard in `coordinator.async_write()`, and pass `config_entry` to the `DataUpdateCoordinator` constructor. The climate entity needs special handling for atomic multi-write preset operations.

**Major components and changes needed:**
1. `coordinator.py` — Add `ConfigEntryAuthFailed` on persistent auth failure; add `config_entry` parameter; add RO guard in `async_write()`
2. `__init__.py` — Distinguish `ConfigEntryAuthFailed` vs `ConfigEntryNotReady` on setup failures
3. Entity platforms (`switch.py`, `number.py`, `climate.py`, `select.py`) — Wrap writes in try/except; raise `HomeAssistantError`; move optimistic updates after successful write
4. `diagnostics.py` — Add attribute catalog dump to diagnostic output
5. CI workflows — Add `schedule` and `workflow_dispatch` triggers; add pytest workflow

### Critical Pitfalls

1. **HACS default repository rejection from missing metadata** — Set GitHub description, topics, and publish at least one GitHub Release before submitting PR to hacs/default. Tags alone are insufficient; a full Release object is required.
2. **Entity unique ID changes break user automations and history** — Treat `entity_key_for_attr()` output as an immutable contract from v1.0.0. Any future change requires `async_migrate_entry()` and a `ConfigFlow.VERSION` bump. Add a regression test.
3. **Optimistic state without rollback erodes user trust** — Fix by moving optimistic updates after the write await. On failure, raise `HomeAssistantError` so HA shows a user-visible error toast. Climate presets need atomic snapshot/rollback for multi-write operations.
4. **WriteData `"20.0"` formatting causes SOAP FormatException** — Use `.rstrip('0').rstrip('.')` to produce `"20"` for integers and `"20.5"` for decimals. Already documented in MEMORY.md. Fix before v1.
5. **No release workflow means manual, error-prone releases** — Add `.github/workflows/release.yaml` triggered on `v*` tags. Without it, HACS users risk version mismatches between `manifest.json` and the git tag.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Code Quality — Bug Fixes and HA Pattern Compliance

**Rationale:** Ship correct write behavior before any users install the integration. These are known bugs documented in CONCERNS.md that will generate immediate user complaints. Fix them first so the v1 release is trustworthy from day one. All fixes are targeted refactors within existing files with no architectural changes.
**Delivers:** Integration that handles write failures correctly with user-visible error toasts, triggers reauth flow when credentials expire, correctly formats SOAP write values, and guards against writes to read-only attributes.
**Addresses:** Optimistic state fix, WriteData decimal fix, number step from metadata, climate RO guard, action exceptions (HomeAssistantError), ConfigEntryAuthFailed, coordinator config_entry parameter.
**Avoids:** Pitfall 3 (optimistic state erodes trust), Pitfall 7 (climate RO writes), WriteData FormatException gotcha.
**Research flag:** Standard HA patterns — no deeper research needed. All patterns documented in official HA developer docs.

### Phase 2: CI and Release Pipeline

**Rationale:** CI must be green before creating the first public release. Establishing the release workflow before tagging v1 ensures HACS can track versions correctly from the start and prevents broken releases from reaching users.
**Delivers:** pytest GitHub Actions workflow with coverage reporting, updated HACS/hassfest workflows (schedule + workflow_dispatch triggers), release automation workflow (tag-triggered GitHub Release creation), confirmed hassfest passing on current codebase.
**Addresses:** CI pytest workflow, GitHub Releases, release automation.
**Avoids:** Pitfall 4 (manual error-prone releases), Pitfall 5 (hassfest failures blocking HACS inclusion).
**Research flag:** Standard patterns — HACS blueprint repository provides reference workflow. No deeper research needed.

### Phase 3: Pre-Release Checklist and HACS Submission

**Rationale:** Repository metadata, brand assets, and README quality are the final gate before submitting to the HACS default repository. These items are quick but easy to forget under release pressure. Complete them in a dedicated phase against an explicit checklist.
**Delivers:** GitHub repo description and topics set; `logo.png` added to `brand/`; PR submitted to `home-assistant/brands`; README enhanced with HACS badge, install instructions, and known limitations; empty catalog warning implemented; version bumped to `1.0.0` in manifest.json; first GitHub Release created; PR submitted to hacs/default.
**Addresses:** GitHub repo metadata, brand assets, empty GetTypeInfo warning, HACS default submission.
**Avoids:** Pitfall 1 (HACS default rejection), brand asset incompleteness, version 0.x trust perception issue.
**Research flag:** Standard HACS submission checklist — fully documented. No unknowns.

### Phase 4: v1.x Enhancements (Post-Stability)

**Rationale:** Once v1.0.0 is live and stable for 2-4 weeks, add features based on actual user feedback. Do not add these before v1 — they increase scope without being required for trust or HACS acceptance.
**Delivers:** Release automation refinements, GitHub issue templates, German translations, manual refresh service, device info enrichment from API, diagnostics catalog dump.
**Addresses:** v1.x features from the FEATURES.md differentiator list.
**Research flag:** German translations and manual refresh service are standard patterns. Device info enrichment requires checking what GetDevices/GetTypeInfo actually returns — needs a quick investigation during phase planning before committing to implementation.

### Phase Ordering Rationale

- Phase 1 before Phase 2: Fix bugs before creating CI that validates them. The pytest workflow in Phase 2 will immediately validate Phase 1 work.
- Phase 2 before Phase 3: A published GitHub Release is a hard dependency for HACS default submission. Cannot submit without it.
- Phase 3 before Phase 4: HACS default listing drives user adoption. Enhancements have more value once there is a user base.
- The unique ID contract must be locked down in Phase 1 before any release. Once v1 ships, it is immutable.

### Research Flags

Phases needing deeper research during planning:
- **Phase 4 (device info enrichment):** Needs quick investigation of what GetDevices and GetTypeInfo actually return for model/firmware fields. Check against WSDL or test with real device before committing to implementation. If unavailable, fall back to static "Viessmann" manufacturer string.

Phases with standard patterns (skip research-phase):
- **Phase 1:** All HA patterns are documented in official developer docs. Straightforward targeted refactoring.
- **Phase 2:** HACS blueprint and GitHub Actions patterns are well-established.
- **Phase 3:** HACS submission checklist is fully documented with no unknowns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All manifest fields verified against HACS docs; existing stack requires no changes |
| Features | HIGH | Based on codebase inspection + HACS requirements + CONCERNS.md; gap list is complete |
| Architecture | HIGH | All patterns from official HA developer docs; codebase inspected for current gaps |
| Pitfalls | HIGH | HACS requirements verified against official docs; code-specific pitfalls from CONCERNS.md |

**Overall confidence:** HIGH

### Gaps to Address

- **Device info fields from API:** Whether GetDevices or GetTypeInfo returns model/firmware is unknown without testing. Low risk — if unavailable, use static "Viessmann" manufacturer string. Address in Phase 4 planning.
- **logo.png design:** The brand logo must be created from scratch. It must not use HA branding and should be a landscape Viessmann/Vitotrol logo. This is a design task, not a code task. Coordinate asset creation before Phase 3.
- **Real-device write testing for climate presets:** The atomic multi-write rollback pattern is architecturally correct but the climate-specific implementation has MEDIUM confidence. Needs validation against a real device or detailed API response mocking.

## Sources

### Primary (HIGH confidence)
- [HACS Integration Publishing Requirements](https://www.hacs.xyz/docs/publish/integration/) — brand assets, manifest, structure
- [HACS General Publishing Requirements](https://www.hacs.xyz/docs/publish/start/) — description, topics, readme, hacs.json
- [HACS Default Repository Inclusion](https://www.hacs.xyz/docs/publish/include/) — automated checks and rejection criteria
- [HACS GitHub Action](https://www.hacs.xyz/docs/publish/action/) — CI validation checks list
- [HA Developer Docs: Handling Setup Failures](https://developers.home-assistant.io/docs/integration_setup_failures/) — ConfigEntryAuthFailed, ConfigEntryNotReady
- [HA Quality Scale: action-exceptions](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-exceptions/) — HomeAssistantError / ServiceValidationError
- [HA Quality Scale: reauthentication-flow](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow/) — reauth flow requirements
- [Home Assistant Brands Repository](https://github.com/home-assistant/brands) — custom_integrations directory structure
- [HA 2026.3 Brand Proxy API](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/) — in-repo brand/ directory support
- Codebase inspection of `custom_components/vitotrol/` — current implementation analysis
- `.planning/codebase/CONCERNS.md` — known bugs and tech debt

### Secondary (MEDIUM confidence)
- [HA Architecture Discussion #1073](https://github.com/home-assistant/architecture/discussions/1073) — coordinator config_entry pattern
- [Peblar coordinator reauth PR](https://github.com/home-assistant/core/pull/162919) — silent re-login pattern example
- [Hassfest for custom components](https://developers.home-assistant.io/blog/2020/04/16/hassfest/) — older post, action still current

---
*Research completed: 2026-03-04*
*Ready for roadmap: yes*
