# Technology Stack: HACS Submission Requirements

**Project:** Vitotrol HASS - Ship to HACS
**Researched:** 2026-03-04
**Mode:** Ecosystem (HACS publishing pipeline)

## Current State Assessment

The integration already has most infrastructure in place. This document identifies the exact gaps and specifies what each file must contain.

### What Already Exists (Verified)

| Asset | Status | Gap |
|-------|--------|-----|
| `manifest.json` | Present, valid | Missing: no gaps for HACS (all 6 required keys present) |
| `hacs.json` | Present | Consider updating `homeassistant` min version |
| `brand/icon.png` | Present (256x256) | Missing: `logo.png` for full branding |
| `brand/icon@2x.png` | Present (512x512) | Good |
| `.github/workflows/hacs.yaml` | Present | Missing: `workflow_dispatch` trigger |
| `.github/workflows/hassfest.yaml` | Present | Missing: `schedule` and `workflow_dispatch` triggers |
| `strings.json` | Present | Good |
| `translations/en.json` | Present | Good |
| GitHub releases | **MISSING** | Required for HACS default submission |
| Repository topics | **UNKNOWN** | Required for HACS default submission |
| Repository description | **UNKNOWN** | Required for HACS default submission |

## Recommended Stack

### manifest.json (Integration Manifest)

**Location:** `custom_components/vitotrol/manifest.json`

All 6 required keys are present in the current file. No changes needed for HACS compatibility.

| Field | Required | Current Value | Status |
|-------|----------|---------------|--------|
| `domain` | YES | `"vitotrol"` | OK |
| `name` | YES | `"Viessmann Vitotrol"` | OK |
| `version` | YES | `"0.1.8"` | OK - bump per release |
| `documentation` | YES | `"https://github.com/benvanmierloo/ha-vitotrol"` | OK |
| `issue_tracker` | YES | `"https://github.com/benvanmierloo/ha-vitotrol/issues"` | OK |
| `codeowners` | YES | `["@benvanmierloo"]` | OK |
| `config_flow` | Recommended | `true` | OK |
| `integration_type` | Recommended | `"hub"` | OK |
| `iot_class` | Recommended | `"cloud_polling"` | OK |
| `requirements` | As needed | `["defusedxml>=0.7.1"]` | OK |

**Version format:** Must be a valid CalVer or SemVer string. Current SemVer (`0.1.8`) is fine. HACS uses the `version` field from manifest.json for display, but the **Git tag** from the latest GitHub Release is the authoritative version for HACS.

**Confidence:** HIGH -- verified against HACS docs and hassfest validation requirements.

### hacs.json (HACS Manifest)

**Location:** Repository root `/hacs.json`

| Field | Required | Current Value | Recommendation |
|-------|----------|---------------|----------------|
| `name` | YES | `"Viessmann Vitotrol"` | OK |
| `homeassistant` | Optional | `"2024.12.0"` | Update to `"2025.1.0"` or current stable when shipping |
| `render_readme` | Optional | `true` | OK -- renders README.md in HACS UI instead of info.md |
| `content_in_root` | Optional | not set | Not needed (standard `custom_components/` layout) |
| `zip_release` | Optional | not set | Not needed |
| `hide_default_branch` | Optional | not set | Not needed |
| `country` | Optional | not set | Not needed (not country-specific) |
| `hacs` | Optional | not set | Not needed unless requiring a minimum HACS version |
| `persistent_directory` | Optional | not set | Not needed |

**Confidence:** HIGH -- verified against HACS publisher docs.

### Brand Assets

**Location:** `custom_components/vitotrol/brand/` (in-repo, supported since HA 2026.3)

Also submit to `home-assistant/brands` repo under `custom_integrations/vitotrol/` for users on older HA versions and for HACS default repository validation.

| File | Required | Size | Status |
|------|----------|------|--------|
| `icon.png` | YES (HACS default) | 256x256 px | Present |
| `icon@2x.png` | Recommended | 512x512 px | Present |
| `logo.png` | Recommended | Shortest side 128-256 px, landscape | **MISSING** |
| `logo@2x.png` | Recommended | Shortest side 256-512 px, landscape | **MISSING** |
| `dark_icon.png` | Optional | 256x256 px | Not present |
| `dark_icon@2x.png` | Optional | 512x512 px | Not present |
| `dark_logo.png` | Optional | Shortest side 128-256 px | Not present |
| `dark_logo@2x.png` | Optional | Shortest side 256-512 px | Not present |

**Image specifications (all files):**
- Format: PNG only
- Compression: lossless preferred, optimized for web
- Interlaced/progressive encoding preferred
- Transparency preferred (no opaque backgrounds)
- Trim empty space around edges -- no borders or padding
- Custom integrations must NOT use Home Assistant branded imagery

**Confidence:** HIGH -- verified against home-assistant/brands README and HA 2026.3 blog post.

### GitHub Actions (CI/CD)

**Location:** `.github/workflows/`

#### HACS Validation (`hacs.yaml`)

Current file is functional but missing recommended triggers.

```yaml
name: HACS Validation

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:

permissions: {}

jobs:
  hacs:
    name: HACS Validation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration
```

**Changes needed:** Add `workflow_dispatch` trigger and `permissions: {}` block.

#### Hassfest Validation (`hassfest.yaml`)

Current file is missing schedule and workflow_dispatch triggers.

```yaml
name: Validate with hassfest

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:

jobs:
  hassfest:
    name: hassfest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master
```

**Changes needed:** Add `schedule` and `workflow_dispatch` triggers.

**Confidence:** HIGH -- workflow YAML verified against HACS action docs.

### GitHub Release Process

HACS reads versions from GitHub Releases (not just tags). Each release must:

1. **Tag format:** `v{version}` (e.g., `v1.0.0`). The tag name becomes the version displayed in HACS.
2. **Full release, not draft/pre-release:** HACS only picks up published releases.
3. **manifest.json version must match:** The `version` field in `manifest.json` should match the tag (without `v` prefix).
4. **Release notes:** Include changelog -- HACS displays these to users.

**Recommended release workflow:**

```bash
# 1. Update version in manifest.json
# 2. Commit: "release: v1.0.0"
# 3. Tag and push
git tag v1.0.0
git push origin v1.0.0
# 4. Create GitHub Release from the tag (use GitHub UI or gh CLI)
gh release create v1.0.0 --title "v1.0.0" --notes "Changelog here"
```

**Optional: Automated release workflow** -- Consider adding a GitHub Actions workflow that creates a release when a tag is pushed. Not required for HACS but reduces manual steps.

**Confidence:** HIGH -- verified against HACS publisher docs.

### Repository Metadata (GitHub Settings)

Required for HACS default repository inclusion:

| Setting | Required | Recommendation |
|---------|----------|----------------|
| Description | YES | "Home Assistant custom integration for Viessmann Vitotrol heating systems" |
| Topics | YES | `home-assistant`, `hacs`, `viessmann`, `vitotrol`, `custom-component` |
| Issues enabled | YES | Already enabled |
| Not archived | YES | Active repo |

**Confidence:** HIGH -- verified against HACS include docs.

## HACS Default Repository Submission Checklist

To submit to `hacs/default` (so users find it in the HACS store without adding a custom repo URL):

| Requirement | Status | Action Needed |
|-------------|--------|---------------|
| Public GitHub repo | DONE | None |
| Repository description set | CHECK | Set in GitHub settings |
| GitHub topics set | CHECK | Set in GitHub settings |
| Issues enabled | DONE | None |
| README.md present | DONE | None |
| hacs.json valid | DONE | None |
| manifest.json valid | DONE | None |
| HACS Action passes | CHECK | Run and verify |
| Hassfest passes | CHECK | Run and verify |
| Brand assets (icon.png minimum) | DONE | Already in brand/ |
| At least one GitHub Release | MISSING | Create v1.0.0 release |
| Submitter is repo owner | DONE | @benvanmierloo |
| Not a core integration override | DONE | Unique domain |
| PR to hacs/default repo | TODO | Add to `integration` file alphabetically |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Distribution | HACS | HA Core inclusion | Core requires higher bar: code review by HA team, no SOAP deps, strict API patterns. HACS is the right choice for a niche integration. |
| Brand hosting | In-repo `brand/` + brands PR | Only brands repo | In-repo works for HA 2026.3+; brands repo PR covers older versions. Do both. |
| Versioning | SemVer (1.0.0) | CalVer (2026.3.0) | SemVer is conventional for custom integrations. CalVer is used by HA Core itself but unusual for components. |
| Release automation | Manual `gh release create` | GitHub Actions auto-release | Manual is fine for low-frequency releases. Automate later if release cadence increases. |

## Version Strategy

Use semantic versioning. Ship `1.0.0` as the first HACS release (not `0.x` -- signal stability):

- **MAJOR** (2.0.0): Breaking config changes requiring user reconfiguration
- **MINOR** (1.1.0): New entity platforms, new attributes, new features
- **PATCH** (1.0.1): Bug fixes, dependency updates

## Installation (No Changes Needed)

The integration requires only one PyPI dependency:

```bash
# Automatically installed by HA from manifest.json requirements
defusedxml>=0.7.1
```

No additional installation steps. HACS handles cloning to `custom_components/vitotrol/`.

## What NOT To Do (Common HACS Rejection Reasons)

1. **Do not submit without a GitHub Release.** Tags alone are not enough -- HACS requires a full release object.
2. **Do not use HA branded imagery** in icons/logos. This will be rejected to avoid confusion with official integrations.
3. **Do not submit from an organization account.** The PR must come from the repo owner's personal account.
4. **Do not skip the PR template.** Incomplete templates are closed without review.
5. **Do not set `content_in_root: true`** unless files are actually in the repo root (they are not -- standard layout is used).
6. **Do not forget `render_readme: true`** in hacs.json if there is no `info.md` file (already set correctly).
7. **Do not have multiple integration directories** under `custom_components/` -- only one subdirectory allowed.

## Sources

- [HACS Integration Publishing Requirements](https://www.hacs.xyz/docs/publish/integration/) -- HIGH confidence
- [HACS General Publishing Requirements](https://www.hacs.xyz/docs/publish/start/) -- HIGH confidence
- [HACS Default Repository Inclusion](https://www.hacs.xyz/docs/publish/include/) -- HIGH confidence
- [HACS GitHub Action](https://www.hacs.xyz/docs/publish/action/) -- HIGH confidence
- [Home Assistant Brands Repository](https://github.com/home-assistant/brands) -- HIGH confidence
- [HA 2026.3 Brand Proxy API (in-repo brands)](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/) -- HIGH confidence
- [Hassfest for Custom Components](https://developers.home-assistant.io/blog/2020/04/16/hassfest/) -- MEDIUM confidence (older post, but action still current)
