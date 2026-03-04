# Vitotrol HASS Integration

## What This Is

A Home Assistant custom integration for Vitotrol-compatible Viessmann heating systems. Communicates directly with the Viessmann cloud SOAP API — no MQTT broker required. Exposes boiler state and control across six entity platforms (sensor, binary_sensor, climate, switch, number, select) with dynamic attribute discovery via GetTypeInfo.

## Core Value

Users with Viessmann boilers can monitor and control their heating system natively in Home Assistant, with automatic attribute discovery and no manual configuration of datapoints.

## Requirements

### Validated

- ✓ SOAP API client with async wait pattern (RefreshData/WriteData polling) — existing
- ✓ Multi-platform entity support: sensor, binary_sensor, climate, number, select, switch — existing
- ✓ Dynamic attribute discovery via GetTypeInfo (no hardcoded attr IDs) — existing
- ✓ Coordinator with configurable polling interval (default 300s) and automatic re-auth on error — existing
- ✓ Config flow: credential entry (username/password) and options (scan interval) — existing
- ✓ Optimistic state updates for write operations — existing
- ✓ Entity registry pre-seeding (only poll attributes that registered entities need) — existing
- ✓ Diagnostics with password redaction — existing
- ✓ Test suite with coordinator, sensor, climate, config flow, entity helper, and platform coverage — existing

### Active

- [ ] HACS compatibility: hacs.json, manifest.json versioning, brand assets (logo/icon)
- [ ] User-facing README: setup instructions, known limitations (no concurrent sessions), supported platforms
- [ ] Config flow error messages: distinguish auth failure vs network error vs no devices found
- [ ] Optimistic state rollback: revert entity state to actual value when WriteData fails or times out
- [ ] GetTypeInfo empty catalog warning: log and surface diagnostic when no attributes discovered
- [ ] WriteData value formatting: fix decimal → integer conversion; validate step size in Number entity
- [ ] Climate preset mutual exclusion: guard writes to RO attributes (eco_mode/party_mode)
- [ ] Test coverage for uncovered scenarios: optimistic rollback, malformed GetTypeInfo enums, concurrent writes, empty device list
- [ ] Code quality: consistent logging levels, HA coding conventions throughout

### Out of Scope

- Concurrent session management / multi-instance HA support — API limitation (single session per account)
- Batch writes — not supported by Viessmann SOAP API
- On-demand refresh endpoint — API is already 10–15s per cycle; low value
- Entity grouping by heating circuit (HC1/HC2/HC3) — HA UI concern, not integration
- Value history or trend analysis — handled by HA's built-in history
- Local/LAN API (no MQTT, no local API known to exist)

## Context

Port of the Go project [vitotrol2mqtt](https://github.com/benvanmierloo/vitotrol2mqtt) (using [go-vitotrol](https://github.com/maxatome/go-vitotrol)) to a native HA Python integration. The SOAP API is well-understood: async wait pattern (fire → poll → read), all attributes discovered via GetTypeInfo, session cookie re-auth on any error.

Key constraints from the API:
- Requesting unsupported attributes crashes the entire SOAP call (GetTypeInfo prevents this)
- RefreshData takes 10–15s end-to-end; WriteData takes ~4s
- One session per account — concurrent Vitotrol app use conflicts with HA polling

## Constraints

- **Tech stack**: Python async, HA DataUpdateCoordinator, aiohttp, defusedxml — no new deps
- **Compatibility**: Must work with current HA stable release; no deprecated HA APIs
- **Distribution**: HACS — must meet HACS requirements (hacs.json, manifest versioning, GitHub releases)
- **API**: Viessmann SOAP endpoint only — no alternative API available
- **Credentials**: Stored as HA config entry data (standard HA practice); no additional encryption layer

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| GetTypeInfo for discovery (vs hardcoded attr IDs) | Supports all devices dynamically; avoids maintaining a static list | ✓ Good |
| Re-login on any API error (not just auth errors) | Session lifetime unknown; simpler than tracking session age | ✓ Good |
| Optimistic state updates without rollback | Faster UX; but leaves stale state on failure | ⚠️ Revisit — need rollback on failure |
| defusedxml for SOAP parsing | XXE protection; HA already bundles it | ✓ Good |
| WriteData value as integer string | Inferred from go-vitotrol; undocumented API behavior | ⚠️ Revisit — need decimal support for some attrs |

---
*Last updated: 2026-03-04 after initialization*
