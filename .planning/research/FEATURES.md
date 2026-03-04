# Feature Research

**Domain:** Home Assistant custom integration (HACS) -- v1 release readiness
**Researched:** 2026-03-04
**Confidence:** HIGH

## Feature Landscape

This research covers what a shippable v1 HACS integration needs beyond working code. The integration already has functional entity platforms, config flow, coordinator, API client, diagnostics, and a test suite. What follows is what's missing or incomplete for a credible v1 release.

### Table Stakes (Users Expect These)

Features users and HACS reviewers assume exist. Missing these = won't ship or won't be trusted.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **GitHub Releases with version tags** | HACS displays releases for install; without them users get raw main branch. HACS strongly prefers tagged releases. | LOW | Need a release workflow (tag push triggers GitHub Release). manifest.json version must match tag. |
| **CI: pytest workflow** | Tests exist but no CI runs them. Users and reviewers check CI badges. Tests that aren't run in CI are decoration. | LOW | Add pytest GitHub Actions workflow. Already have hacs.yaml and hassfest.yaml. |
| **Optimistic state rollback on write failure** | Users see wrong state for up to 300s when a write fails. This is a known bug (CONCERNS.md). Unacceptable for a climate/switch integration. | MEDIUM | Wrap write calls in try/except, revert coordinator data on failure. High priority bug fix, not a feature. |
| **WriteData decimal handling** | Number entities truncate decimals silently. Setting 20.5 becomes 20. Users will report this as a bug immediately. | LOW | Strip trailing `.0` for integers, pass decimals as-is. Already documented in MEMORY.md. |
| **Number entity step from GetTypeInfo** | Step hardcoded to 1.0; ignores actual attribute precision. UI shows integer-only slider for decimal attributes. | LOW | Parse min/max from GetTypeInfo to infer step (e.g., if min=10.0 max=60.0 with type Double, step=0.5). |
| **Climate preset RO/RW guard** | Writing to a read-only eco/party attribute fails silently. Known bug. | LOW | Check `is_writable` flag before calling async_write. Skip or log warning for RO attributes. |
| **Config flow: distinct error messages** | Already partially done in strings.json (invalid_auth, cannot_connect, no_devices). Verify all three paths are actually triggered correctly. | LOW | Test coverage exists in test_config_flow.py. Verify edge cases. |
| **Reauth flow** | strings.json has reauth_confirm step. Must work end-to-end when session expires. Users expect seamless re-authentication. | LOW | Verify reauth triggers correctly on VitotrolAuthError. HA has standard patterns for this. |
| **GitHub description and topics** | HACS requires a repo description and topics for discoverability. | LOW | Set repo description + topics (home-assistant, hacs, viessmann, vitotrol, heating). |
| **Brand assets in correct location** | HACS requires brand directory with icon.png. Already exists at `custom_components/vitotrol/brand/`. | DONE | icon.png and icon@2x.png present. Verify they meet HACS size/format requirements (256x256 PNG). |
| **Empty catalog warning** | GetTypeInfo returning zero attributes silently produces an integration with no entities. Users will file bugs. | LOW | Log warning + create a repair issue or persistent notification if catalog is empty. |

### Differentiators (Competitive Advantage)

Features that make this integration stand out in HACS. Not required, but increase trust and adoption.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **GitHub issue/bug report templates** | Guides users to include diagnostics JSON and attribute catalog. Reduces back-and-forth on issues. README already explains how to share attributes. | LOW | Add `.github/ISSUE_TEMPLATE/bug_report.yml` and `feature_request.yml` with structured fields. |
| **Release automation workflow** | Tag-triggered workflow that creates a GitHub Release automatically. Reduces manual release friction, ensures manifest version stays in sync. | LOW | Common pattern: on tag push, create release. Can also auto-bump manifest.json version. |
| **HACS default repository submission** | Getting into the HACS default repository list means users find it by searching in HACS without adding a custom repo URL. Massive discoverability boost. | LOW (effort) | Submit PR to https://github.com/hacs/default after v1 is stable. Requires passing hacs/action validation (already set up). |
| **Diagnostics with attribute catalog dump** | Already have diagnostics.py with password redaction. Including the full GetTypeInfo catalog in diagnostics makes debugging trivial. | LOW | May already be included. Verify diagnostics output contains device attributes and catalog metadata. |
| **Device info with firmware/model from API** | HA device registry shows manufacturer, model, sw_version. If the API provides any of these, surface them. Makes the Devices page informative. | LOW-MEDIUM | Check if GetDevices or GetTypeInfo returns model/firmware info. If not, use static "Viessmann" manufacturer + device name. |
| **Service for manual data refresh** | Users want to trigger an immediate poll without waiting 300s. Useful after making changes via the Vitotrol app. | MEDIUM | Register a custom service `vitotrol.refresh_data`. Calls coordinator.async_request_refresh(). Simple wrapper but 10-15s API latency still applies. |
| **Comprehensive translations** | Only English exists. German translations would cover a significant portion of the Viessmann user base (German manufacturer, DACH market). | LOW | Add `translations/de.json`. Most entity names are already English but config flow strings should be translated. |

### Anti-Features (Commonly Requested, Often Problematic)

Features to deliberately NOT include in v1.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Concurrent session support** | Users want to use Vitotrol app and HA simultaneously | API limitation: one session per account. Cannot fix in integration. Adding retry-on-eviction creates a session ping-pong war. | Document limitation clearly. Suggest dedicated account if Viessmann supports it. |
| **On-demand refresh button per entity** | Users want instant updates after changing a thermostat | API takes 10-15s per cycle. Button implies instant result. Creates UX confusion when state doesn't update immediately. | Service call (above) with documented latency, or just wait for next poll. |
| **Entity grouping by heating circuit** | HC1/HC2/HC3 entities are mixed together in the UI | This is a HA UI concern, not integration logic. Adding device-per-circuit inflates device count and complicates the device registry. | Users can organize via HA areas, labels, or custom dashboards. Entity naming already includes circuit prefix. |
| **Batch write operations** | Setting multiple values at once (e.g., set temp + mode) | SOAP API does not support batch writes. Faking it with sequential calls adds complexity and partial-failure states. | Let HA handle sequential service calls via automations/scripts. |
| **Local/LAN API** | Avoid cloud dependency | No known local API exists for Vitotrol devices. Adding MQTT would reintroduce the broker dependency this integration was built to eliminate. | Cloud-only is the reality. Document it as a known limitation. |
| **Value history/trending** | See temperature trends over time | HA's built-in history, statistics, and energy dashboard handle this natively. Duplicating it in the integration adds no value. | Point users to HA's history and statistics features. |
| **Auto-discovery (SSDP/mDNS/DHCP)** | Find devices on the network automatically | Vitotrol is cloud-only. No local discovery protocol exists. | Config flow with manual credential entry is the correct approach for cloud integrations. |

## Feature Dependencies

```
GitHub Releases
    └──requires──> Release automation workflow (optional but recommended)

Optimistic state rollback
    └──requires──> WriteData decimal handling (related value formatting)

Number entity step from GetTypeInfo
    └──requires──> WriteData decimal handling (step implies decimal support)

HACS default repo submission
    └──requires──> GitHub Releases
    └──requires──> CI pytest workflow
    └──requires──> HACS validation passing (already set up)

Climate preset RO/RW guard
    └──requires──> GetTypeInfo metadata (already available in catalog)
```

### Dependency Notes

- **Number step requires decimal handling:** If the step is 0.5, the write path must support sending "20.5" not "20". These are the same underlying fix.
- **HACS default submission requires releases:** The HACS default repository list requires stable releases and passing CI. All table stakes must be done first.
- **Rollback and decimal fixes are independent but related:** Both touch the write path. Fix together to avoid double-refactoring.

## MVP Definition

### Launch With (v1)

Minimum for a credible HACS release that users will trust and reviewers will accept.

- [x] Working entity platforms (sensor, binary_sensor, climate, switch, number, select) -- DONE
- [x] Config flow with credential validation -- DONE
- [x] Diagnostics with redaction -- DONE
- [x] hacs.json, manifest.json, brand assets -- DONE
- [x] HACS validation + hassfest CI -- DONE
- [x] README with install/setup/troubleshooting -- DONE
- [x] strings.json + en.json translations -- DONE
- [ ] CI pytest workflow -- needed
- [ ] GitHub Releases with tagged versions -- needed
- [ ] Optimistic state rollback on write failure -- bug fix, needed
- [ ] WriteData decimal handling fix -- bug fix, needed
- [ ] Number entity step from GetTypeInfo metadata -- needed
- [ ] Climate preset RO/RW guard -- bug fix, needed
- [ ] Empty GetTypeInfo catalog warning -- needed
- [ ] GitHub repo description + topics -- needed

### Add After Validation (v1.x)

Features to add once v1 is stable and users are providing feedback.

- [ ] Release automation workflow -- when manual releases become tedious
- [ ] GitHub issue templates -- when issue volume increases
- [ ] HACS default repository submission -- after v1 has been stable for 2-4 weeks
- [ ] German translations -- after confirming user base interest
- [ ] Manual refresh service -- if users request it frequently
- [ ] Device info enrichment (model/firmware) -- if API provides this data

### Future Consideration (v2+)

Features to defer until the integration has real-world usage data.

- [ ] Session timeout enforcement (24h re-login) -- low risk, document-only for now
- [ ] Disabled entity pruning from poll set -- optimization, only matters at scale
- [ ] Dynamic preset/option refresh on catalog change -- firmware updates are rare

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Optimistic state rollback | HIGH | MEDIUM | P1 |
| WriteData decimal handling | HIGH | LOW | P1 |
| Number entity step from metadata | HIGH | LOW | P1 |
| Climate preset RO/RW guard | MEDIUM | LOW | P1 |
| CI pytest workflow | MEDIUM | LOW | P1 |
| GitHub Releases + tags | HIGH | LOW | P1 |
| Empty catalog warning | MEDIUM | LOW | P1 |
| GitHub repo description + topics | LOW | LOW | P1 |
| Release automation workflow | MEDIUM | LOW | P2 |
| GitHub issue templates | MEDIUM | LOW | P2 |
| HACS default repo submission | HIGH | LOW | P2 |
| German translations | LOW | LOW | P2 |
| Manual refresh service | LOW | MEDIUM | P3 |
| Device info enrichment | LOW | LOW-MEDIUM | P3 |
| Session timeout enforcement | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for v1 launch
- P2: Should have, add in v1.x
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | viessmann (official HA) | ha-vicare (HACS) | Our Approach |
|---------|------------------------|-------------------|--------------|
| API | Viessmann API v2 (OAuth2, REST) | ViCare API (newer devices) | Vitotrol SOAP API (older devices) |
| Device support | Newer Viessmann devices only | ViCare-compatible devices | Vitotrol-compatible devices (fills a gap) |
| Config flow | Yes | Yes | Yes |
| Climate entity | Yes | Yes | Yes, with ECO/Boost presets |
| Auto-discovery | No (cloud) | No (cloud) | No (cloud) -- correct for cloud integrations |
| Diagnostics | Yes | Varies | Yes, with password redaction |
| Dynamic attr discovery | No (fixed entities) | No (fixed entities) | Yes (GetTypeInfo) -- this is a differentiator |
| GitHub Releases | Yes | Yes | Needed |
| Translations | Multiple | English | English (German planned) |

**Key differentiator:** Dynamic attribute discovery via GetTypeInfo. Users don't need to wait for integration updates when their device supports new attributes. All discovered attributes are automatically created as entities (disabled by default). No other Viessmann integration does this.

**Market position:** This integration serves Vitotrol-compatible devices (older Viessmann systems) that are NOT supported by the official Viessmann integration or ViCare. It fills a gap, not competes.

## Sources

- [HACS Integration Publishing Requirements](https://www.hacs.xyz/docs/publish/integration/) -- repository structure, manifest, brand assets
- [HACS General Publishing Requirements](https://www.hacs.xyz/docs/publish/start/) -- description, topics, readme, hacs.json
- [Home Assistant Quality Scale](https://www.home-assistant.io/docs/quality_scale/) -- Bronze/Silver/Gold/Platinum tier requirements
- [Home Assistant Backend Localization](https://developers.home-assistant.io/docs/internationalization/core/) -- strings.json best practices
- Project codebase analysis (manifest.json, hacs.json, strings.json, CI workflows, test suite)
- CONCERNS.md -- known bugs and tech debt informing P1 priorities

---
*Feature research for: Vitotrol HASS v1 HACS release*
*Researched: 2026-03-04*
