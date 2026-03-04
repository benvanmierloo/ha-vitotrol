# Pitfalls Research

**Domain:** Home Assistant custom integration shipping to HACS
**Researched:** 2026-03-04
**Confidence:** HIGH (HACS requirements verified against official docs; HA deprecations verified against changelogs and community reports; codebase-specific pitfalls verified against CONCERNS.md)

## Critical Pitfalls

### Pitfall 1: HACS Default Repository Rejection Due to Missing Repository Metadata

**What goes wrong:**
The HACS GitHub Action and the default-repository inclusion review run automated checks that reject repositories for missing non-obvious metadata: no GitHub topics set, no repository description, issues not enabled, no `brand/` directory with `icon.png`, no published GitHub Release (tags alone are insufficient), and no `hacs.json` with at least a `name` field. These are repo-level settings, not code issues, so developers miss them entirely.

**Why it happens:**
Developers focus on code quality and forget that HACS validates the GitHub repository itself. The HACS Action checks: archived status, brands, description, hacs manifest, information (README), issues enabled, and topics. The default-repo PR also runs: releases check, owner verification, JSON linting, alphabetical file sorting. Missing any blocks inclusion.

**How to avoid:**
1. Run the HACS Action (`hacs/action@main`) in CI -- already done at `.github/workflows/hacs.yaml`.
2. Before submitting to hacs/default, verify the GitHub repo has: a description, at least 3 topics (e.g., `home-assistant`, `hacs`, `viessmann`), issues enabled, and at least one published Release (not draft, not prerelease).
3. The `brand/` directory has `icon.png` and `icon@2x.png` -- good. Add `logo.png` for the full brand experience (HA 2026.3+ supports custom integration brand images from the `brand/` directory). Also submit a PR to `home-assistant/brands` under `custom_integrations/vitotrol/` for users on HA < 2026.3.
4. Submit the hacs/default PR from the repo owner's personal GitHub account (@benvanmierloo), not an organization. Fill out every checkbox in the PR template.

**Warning signs:**
- HACS Action CI job fails or has never been run against the actual remote repo.
- No GitHub Releases exist yet.
- `gh release list` returns empty.
- Repository has no topics or description set.

**Phase to address:**
Pre-release checklist phase. All items are quick fixes but easy to forget under release pressure.

---

### Pitfall 2: Entity Unique ID Changes Break User Automations and History

**What goes wrong:**
If the `unique_id` format changes between versions (e.g., refactoring from `{device_id}_{key}` to `{device_id}_{attr_id}`), all existing entities get orphaned in the entity registry. Users lose their automation references, dashboard cards, history data, and entity customizations (friendly names, area assignments). This is the single most destructive breaking change a custom integration can ship.

**Why it happens:**
Developers refactor entity key generation without realizing that `unique_id` is a permanent contract with the user's HA instance. The current implementation uses `entity_key_for_attr()` which generates keys from attribute names for known attrs (`indoor_temperature`) and `attr_{id}` for unknown ones. If `AttrMeta.name` values change, or the lowercasing/underscore replacement logic changes, every entity silently gets a new identity.

**How to avoid:**
1. Never change the `unique_id` format without a migration path. If a change is absolutely needed, implement `async_migrate_entry()` in `__init__.py` and bump `ConfigFlow.VERSION`.
2. Document the `unique_id` contract explicitly: `{device_id}_{lowercase_name_with_underscores}` for known attrs, `{device_id}_attr_{attr_id}` for unknown attrs.
3. Add a regression test that asserts specific known unique_ids match expected values (e.g., `assert entity_key_for_attr(5367, indoor_temp_meta) == "indoor_temperature"`).
4. The `tests/test_entity_helpers.py` already tests key generation -- keep this test and treat its failure as a release blocker.

**Warning signs:**
- Any PR that modifies `entity_key_for_attr()` or `AttrMeta.name` values in `attributes.py`.
- Entity platform tests that check unique_ids start failing.
- After upgrading: users report "entity not found" errors in automations.

**Phase to address:**
Must be locked down before v1.0.0 release. Any post-release format change requires migration code.

---

### Pitfall 3: Optimistic State Without Rollback Erodes User Trust

**What goes wrong:**
Write operations (climate set_temperature, switch toggle, number set_value, select set_option) update the coordinator's in-memory data immediately via `_update_coordinator_data()`. If the Viessmann API write fails (network error, timeout after 60s, invalid value, writing to a read-only attribute), the entity shows the wrong state for up to 300 seconds until the next scheduled poll. Users see "success" but the boiler did not actually change.

**Why it happens:**
Optimistic updates are a standard HA pattern for snappy UX, but most integrations that use them either have fast confirmation (local devices respond in <1s) or implement rollback. The Viessmann SOAP API is uniquely slow (4-15s per write operation) with an async fire-and-poll model, making optimistic updates riskier than usual. The `CONCERNS.md` documents this as a known tech debt issue.

**How to avoid:**
1. Wrap the `coordinator.async_write()` call in try/except. On failure, revert the coordinator data to the pre-write value and call `self.async_write_ha_state()`.
2. After a successful write, force an immediate coordinator data refresh to confirm the actual device state rather than trusting the optimistic value for 300s.
3. Log warnings for write failures so users can check the HA log.
4. Test the rollback path: mock a failing `write_data_wait()` and verify the entity state reverts.

**Warning signs:**
- Users report "I set the temperature but nothing happened."
- Entity shows a value that does not match the physical device for extended periods.
- Bug reports about "stuck" entity states that only fix on reload.

**Phase to address:**
Pre-release bug fix phase. Listed in PROJECT.md Active requirements. Must ship with v1.

---

### Pitfall 4: No Automated Release Workflow Means Manual, Error-Prone Releases

**What goes wrong:**
Without an automated release workflow, the developer must manually: bump `manifest.json` version, commit, create a git tag, push the tag, create a GitHub Release with notes. Missing any step means HACS users either cannot update or get a broken update. Common mistakes: version in `manifest.json` does not match the git tag, forgetting to create an actual GitHub Release object (just pushing a tag is insufficient for HACS), or including development files in the release.

**Why it happens:**
Developers assume "push tag = release." HACS specifically requires a GitHub Release object (created via GitHub UI or API), not just a git tag. Without automation, every release is a manual multi-step process with no validation.

**How to avoid:**
1. Create a `.github/workflows/release.yaml` that triggers on tag push (`v*`), validates the version matches `manifest.json`, runs HACS Action + hassfest as gates, and creates a GitHub Release automatically.
2. Use the standard pattern from the HACS blueprint repository as a template.
3. Consider using `gh release create v1.0.0 --generate-notes` for the initial release.

**Warning signs:**
- No `.github/workflows/release.yaml` exists (currently missing from this repo).
- HACS shows "no releases available" for the repo.
- `manifest.json` version does not match the latest git tag.

**Phase to address:**
CI/release pipeline phase. Must be in place before the first public release.

---

### Pitfall 5: Hassfest Validation Failures Blocking HACS Inclusion

**What goes wrong:**
Hassfest validates `manifest.json` structure, translation file consistency, domain uniqueness, integration type, and dependency declarations. Common failures include: `strings.json` and `translations/en.json` being out of sync, `requirements` listing packages with version pins incompatible with what HA bundles, translation keys missing for new entity platforms, and `integration_type` not matching the actual integration behavior.

**Why it happens:**
Hassfest checks evolve with each HA release. A manifest that passed six months ago may fail today. Developers add new entity platforms or config flow steps but forget to update translation files.

**How to avoid:**
1. Run hassfest in CI on every push -- already done at `.github/workflows/hassfest.yaml`.
2. Keep `translations/en.json` in exact sync with `strings.json`. When adding entity translation keys or config flow steps, update both files simultaneously.
3. Ensure `manifest.json` version follows semver (currently `0.1.8` -- valid).
4. The `defusedxml>=0.7.1` requirement is fine because HA bundles defusedxml. Verify the pinned version does not conflict with what HA ships.
5. Run hassfest locally before releases: `docker run --rm -v $(pwd):/github/workspace ghcr.io/home-assistant/hassfest`.

**Warning signs:**
- Hassfest CI job fails after adding new platforms or translation keys.
- `strings.json` has entity keys that `translations/en.json` does not (or vice versa).
- Adding a new entity type without adding its translation block.

**Phase to address:**
CI/release pipeline phase. Should be validated in CI before every release tag.

---

### Pitfall 6: HA Version Compatibility Breaks From Deprecated APIs

**What goes wrong:**
Home Assistant deprecates internal APIs with ~6-month grace periods. In HA 2025.1, explicitly setting `config_entry` on option flows was deprecated (removed in 2025.12). Climate entity state attributes were migrated to dedicated entities. Reauth/reconfigure flows must be linked to a config entry via `entry.async_start_reauth(hass)`. Custom integrations that use deprecated patterns break on the removal date, flooding user logs with warnings and eventually failing entirely.

**Why it happens:**
Custom integration authors test against one HA version and do not track HA release notes for deprecation notices. The deprecation period (6 months) creates a false sense of security.

**How to avoid:**
1. This codebase uses `OptionsFlowWithReload` and does not explicitly set `self.config_entry` -- good, the major 2025 deprecation is already avoided.
2. The reauth flow uses `self._get_reauth_entry()` which is the current correct pattern.
3. Subscribe to the HA developer blog RSS feed; check changelogs before each release.
4. Set `hacs.json` `homeassistant` to a tested minimum version (currently `2024.12.0`). Bump this when you rely on APIs that did not exist in older versions.
5. Consider adding a CI job that tests against the HA beta Docker image to catch deprecations early.

**Warning signs:**
- HA logs show deprecation warnings mentioning `vitotrol`.
- Hassfest CI starts failing after an HA core update.
- Users report the integration stops loading after updating HA.

**Phase to address:**
Ongoing maintenance. Initial CI setup should include HA beta testing. Address in CI/release pipeline phase.

---

### Pitfall 7: Climate Preset Writes to Read-Only Attributes

**What goes wrong:**
The climate entity's `async_set_preset_mode()` writes to `eco_attr` and `party_attr` if they are not None, assuming both are writable. If a device has a read-only eco_mode but a writable party_mode (or vice versa), the write to the RO attribute fails. The entity state was already updated optimistically, so the user sees a successful preset change that did not actually happen.

**Why it happens:**
The original code was written for one known device configuration. Different Viessmann models expose different combinations of RO/RW eco and party mode attributes. The `CONCERNS.md` documents this as a known bug.

**How to avoid:**
1. Check `AttributeTypeInfo.is_writable` before attempting any write. Skip RO attributes with a debug log.
2. Only offer presets in `supported_preset_modes` if the required attributes are writable.
3. Add a unit test with a device that has mismatched RO/RW eco/party attrs.

**Warning signs:**
- Users with certain Viessmann models report that preset changes do not take effect.
- HA logs show WriteData errors for specific attribute IDs.

**Phase to address:**
Pre-release bug fix phase. Known bug that must be fixed before v1.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoded step=1.0 in Number entity | Simpler code, works for known integer attrs | Decimal-valued attrs show wrong UI slider; writes truncate values silently | Acceptable for v1 only if documented; fix when decimal attrs are discovered |
| WriteData int conversion (`str(int(float(value)))`) | Matches inferred go-vitotrol behavior | `FormatException` for `"20.0"` sent to API; silent rounding for decimal attrs | Never -- fix before v1 using the `.rstrip('0').rstrip('.')` pattern documented in MEMORY.md |
| German name parsing for metadata inference | Auto-discovers device_class/unit for unknown attrs | Breaks silently if API changes language; wrong inference produces incorrect units | Acceptable with fallback to "no unit"; add regression tests for common German patterns |
| Polling all registered attrs including disabled entities | Simpler coordinator; no entity-enable tracking | Wasted API bandwidth; slower refresh on devices with many disabled entities | Acceptable for v1; revisit if users report slow updates with 100+ entities |
| No connection mutex for concurrent writes | Simpler entity code; HA event loop is single-threaded | Safe today but fragile assumption; no documentation of why it is safe | Acceptable -- add inline comment documenting the single-threaded safety assumption |

## Integration Gotchas

| Integration Point | Common Mistake | Correct Approach |
|-------------------|----------------|------------------|
| Viessmann SOAP API | Requesting attrs the device does not support (crashes entire SOAP call) | Always filter valid attr_ids through GetTypeInfo catalog before GetData/RefreshData |
| Viessmann SOAP API | Sending `"20.0"` for integer attrs (causes `FormatException`) | Strip trailing zeros: `"20.0"` -> `"20"`, `"20.5"` -> `"20.5"` |
| Viessmann SOAP API | Assuming session cookies persist indefinitely | Re-login on any API error; consider forced re-login every 24h |
| Viessmann SOAP API | Using Vitotrol mobile app while HA polls (single session per account) | Document prominently; log info message on re-auth events |
| HA Entity Registry | Changing `unique_id` format between versions | Treat `unique_id` as immutable; use `async_migrate_entry()` for any schema changes |
| HA Config Flow | Storing credentials then changing config entry schema without migration | Bump `ConfigFlow.VERSION` and implement `async_migrate_entry()` before shipping |
| HACS Publishing | Creating a git tag without a GitHub Release object | Use a release workflow that creates an actual Release from the tag |
| HACS Default Repo | Adding entry out of alphabetical order in hacs/default integration list | Sort manually or use `jq` before submitting PR |
| HA Brands | Putting brand assets only in the repo `brand/` directory | Also submit PR to `home-assistant/brands` under `custom_integrations/vitotrol/` for HA < 2026.3 |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Polling all 200+ attrs every refresh cycle | Refresh takes 10-15s; API may rate limit | Only poll attrs for enabled entities; add entity-enable callback to coordinator | Devices with 500+ attrs and many disabled entities |
| Sequential writes for climate preset changes (2-3 API calls) | 4-8s visible UI delay when switching presets | Cannot batch (API limitation); document the delay; ensure optimistic update gives immediate feedback | Already noticeable with current API latency |
| GetTypeInfo called once at setup with no recovery | Empty catalog = zero entities created, no error shown to user | Log warning if catalog has fewer than 5 attrs; retry GetTypeInfo on next coordinator update | Transient API failure during HA startup |
| No debounce on rapid user writes | Multiple rapid slider adjustments each trigger a full write-poll cycle | Add a short debounce (1-2s) before committing writes, or cancel pending writes when a new one arrives | Users rapidly adjusting temperature slider |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging credentials in debug output | Password visible in HA logs shared for support | Audit all `_LOGGER.debug()` calls; never log password or raw SOAP request bodies |
| Diagnostics not redacting all sensitive fields | Password exposed in diagnostic dumps users share publicly | Verify `async_get_config_entry_diagnostics()` redacts password from both `data` and `options` dicts |
| No session timeout enforcement | Stale session cookie used indefinitely without re-validation | Add `last_login_time` tracking; force re-login after 24h even without errors |
| Custom `_xml_escape()` instead of stdlib | Edge cases in XML escaping could allow injection | Current implementation covers the five XML entities correctly; but migrating to `xml.etree.ElementTree` for body construction would be more robust |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| 300s default poll interval with no explanation | User changes a setting, sees no update for 5 minutes, thinks integration is broken | Document the poll interval in README; add a note in the options flow UI explaining the tradeoff |
| Unknown attributes created as disabled entities with names like `attr_7855` | User enables an entity and sees no context for what it does | Use `DatenpunktName` from GetTypeInfo as the display name for unknown attrs |
| Optimistic state shows "success" but write actually failed | User trusts the displayed value; boiler did not change | Implement rollback on failure; log a persistent notification for failed writes |
| No indication of API session conflict with mobile app | Integration silently re-logins, potentially kicking user from Vitotrol app | Log info message when re-auth occurs; document single-session limitation in README |
| Config flow shows generic "cannot_connect" for server errors | User cannot tell if it is a network problem, API downtime, or account issue | Already has distinct error keys (`cannot_connect`, `no_devices`, `invalid_auth`) -- verify each maps to the right failure mode |
| Version 0.x signals "not production ready" | Users hesitate to install a 0.x integration for their heating system | Ship v1.0.0 as the first public HACS release if the integration is tested and working |

## "Looks Done But Isn't" Checklist

- [ ] **Brand assets:** `icon.png` exists but `logo.png` is missing -- HA 2026.3+ uses `logo.png` for integration page display. Add it.
- [ ] **GitHub Release:** No release workflow exists. Tags alone are not sufficient for HACS default-repo inclusion.
- [ ] **README for HACS:** `render_readme: true` is set in `hacs.json`, but the README must contain HACS installation badge, setup instructions, screenshots, and known limitations for users to trust the integration.
- [ ] **translations/en.json sync:** Verify it matches `strings.json` exactly. Any drift causes hassfest failure or missing UI text.
- [ ] **Config entry migration:** `ConfigFlow.VERSION = 1` is set, but no `async_migrate_entry()` exists. Must be added before any config schema change ships.
- [ ] **Diagnostics password redaction:** Verify password is redacted in all diagnostic output paths.
- [ ] **Entity naming with devices:** `_attr_has_entity_name = True` is set -- good. Verify all entity `name` properties return only the entity's function (e.g., "Indoor temperature"), not the device name.
- [ ] **Test coverage for write failures:** Optimistic rollback is in Active requirements but has no tests yet. Ship tests before v1.
- [ ] **Climate preset RO/RW guard:** Known bug where writing to read-only eco/party attrs fails silently. Must be fixed before v1.
- [ ] **WriteData value formatting:** The `int(float(value))` pattern strips decimals. Fix to use proper string formatting before v1.
- [ ] **GitHub repo metadata:** Description set, issues enabled, topics assigned (home-assistant, hacs, viessmann, vitotrol).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Unique ID format change | HIGH | Ship migration code in `async_migrate_entry()`; bump ConfigFlow VERSION; users must reload integration; history for old entities is lost forever |
| Optimistic state stuck at wrong value | LOW | Wait for next poll cycle (300s) or reload integration; permanent fix: implement rollback |
| HACS validation failure on submission | LOW | Fix the failing check; push a new release; resubmit PR to hacs/default |
| HA deprecation breaks integration | MEDIUM | Patch the deprecated API call; release hotfix; users must update via HACS |
| WriteData formatting bug causes API error | MEDIUM | Fix conversion logic; release hotfix; incorrect device state from bad writes must be reverted manually on device |
| Brand assets missing or wrong | LOW | Add/fix files in `brand/`; push update; no user-side impact |
| Config schema change without migration | HIGH | Retroactively add migration code; users who upgraded may need to delete and re-add the integration, losing all entity customizations |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| HACS metadata missing (topics, description, releases) | Pre-release checklist | HACS Action CI green; `gh release list` shows at least one release |
| Hassfest failures (translations, manifest) | CI/release pipeline | Hassfest CI green on every push; `strings.json` and `translations/en.json` match |
| Unique ID breakage | Pre-v1 lockdown | Regression test for `entity_key_for_attr()` output; contract documented in code comments |
| Optimistic state no rollback | Pre-release bug fixes | Test for write failure rollback; manual test on real device |
| No release workflow | CI/release pipeline | `.github/workflows/release.yaml` exists; triggers on `v*` tags; creates GitHub Release |
| HA version compatibility | CI/release pipeline | CI job tests against HA beta; `hacs.json` min version is accurate |
| WriteData value formatting | Pre-release bug fixes | Unit test for integer stripping (`"20.0"` -> `"20"`); manual test with real API |
| Climate preset RO guard | Pre-release bug fixes | Unit test for mixed RO/RW preset attrs; no write attempted on RO attributes |
| Brand assets incomplete | Pre-release checklist | `brand/` contains both `icon.png` and `logo.png`; PR to home-assistant/brands submitted |
| README quality for HACS | Pre-release checklist | README has HACS badge, install instructions, screenshots, known limitations |
| Version number perception | Pre-release checklist | First public release is v1.0.0, not v0.x |

## Sources

- [HACS Integration Publishing Requirements](https://www.hacs.xyz/docs/publish/integration/) -- brand, manifest, and structure requirements
- [HACS Default Repository Inclusion](https://www.hacs.xyz/docs/publish/include/) -- automated checks and rejection criteria
- [HACS GitHub Action](https://www.hacs.xyz/docs/publish/action/) -- CI validation checks list
- [Home Assistant Entity Developer Docs](https://developers.home-assistant.io/docs/core/entity/) -- unique_id contract, entity naming
- [HA Config Flow Docs](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/) -- config entry migration
- [HA 2025.1 option flow deprecation](https://github.com/hacs/integration/issues/4314) -- explicit config_entry setting removed in 2025.12
- [Custom integration brand images (HA 2026.3)](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/) -- new brand/ directory support
- [Hassfest for custom components](https://developers.home-assistant.io/blog/2020/04/16/hassfest/) -- CI validation tool
- [Home Assistant Brands Repository](https://github.com/home-assistant/brands) -- custom_integrations directory structure
- `.planning/codebase/CONCERNS.md` -- known bugs and tech debt in this codebase
- `.planning/PROJECT.md` -- active requirements and constraints

---
*Pitfalls research for: Home Assistant custom integration (Vitotrol) shipping to HACS*
*Researched: 2026-03-04*
