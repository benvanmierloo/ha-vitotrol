---
phase: 1
slug: code-quality
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-homeassistant-custom-component |
| **Config file** | `pytest.ini` (root) — `asyncio_mode = auto`, `testpaths = tests` |
| **Quick run command** | `.venv/bin/python -m pytest tests/ -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/ -x -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | HAPAT-01 | unit | `.venv/bin/python -m pytest tests/test_coordinator.py -k config_entry -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | BUGS-06 | unit | `.venv/bin/python -m pytest tests/test_coordinator.py -k auth_failed -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | BUGS-07 | unit | `.venv/bin/python -m pytest tests/test_coordinator.py -k empty_catalog -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | TEST-05 | unit | `.venv/bin/python -m pytest tests/test_coordinator.py -k concurrent -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | BUGS-02 | unit | `.venv/bin/python -m pytest tests/test_api.py -k format -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | BUGS-03 | unit | `.venv/bin/python -m pytest tests/test_number.py -k step -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 2 | BUGS-01, BUGS-05, TEST-02 | unit | `.venv/bin/python -m pytest tests/test_switch.py -k rollback -x` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 2 | BUGS-01, BUGS-04, BUGS-05, TEST-02 | unit | `.venv/bin/python -m pytest tests/test_climate.py -k "rollback or readonly" -x` | ❌ W0 | ⬜ pending |
| 1-02-05 | 02 | 2 | BUGS-01, BUGS-05, TEST-02 | unit | `.venv/bin/python -m pytest tests/test_number.py -k rollback -x` | ❌ W0 | ⬜ pending |
| 1-02-06 | 02 | 2 | BUGS-01, BUGS-05, TEST-02 | unit | `.venv/bin/python -m pytest tests/test_select.py -k rollback -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 2 | HAPAT-02, TEST-04 | unit | `.venv/bin/python -m pytest tests/test_config_flow.py -k no_devices -x` | check existing | ⬜ pending |
| 1-03-02 | 03 | 2 | TEST-03 | unit | `.venv/bin/python -m pytest tests/test_api.py -k malformed -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_coordinator.py` — stubs for BUGS-06, BUGS-07, HAPAT-01, TEST-05
- [ ] `tests/test_api.py` — stubs for BUGS-02, TEST-03
- [ ] `tests/test_switch.py` — stubs for BUGS-01/TEST-02 rollback
- [ ] `tests/test_climate.py` — stubs for BUGS-01/TEST-02, BUGS-04
- [ ] `tests/test_number.py` — stubs for BUGS-01/TEST-02, BUGS-03
- [ ] `tests/test_select.py` — stubs for BUGS-01/TEST-02
- [ ] `tests/test_config_flow.py` — verify/add no_devices test for HAPAT-02/TEST-04

*No new test files required — existing files cover all requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Error toast visible in HA UI on write failure | BUGS-05 | HA toast rendering requires live UI | Trigger a write with mock API error; confirm toast appears in HA dashboard |
| Reauth prompt appears in HA UI | BUGS-06 | HA reauth UI flow requires live instance | Set invalid credentials; trigger poll; confirm reauth notification in HA |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
