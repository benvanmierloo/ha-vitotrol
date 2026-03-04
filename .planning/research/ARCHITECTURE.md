# Architecture Research

**Domain:** Home Assistant custom integration (SOAP API with async polling, DataUpdateCoordinator)
**Researched:** 2026-03-04
**Confidence:** HIGH (based on official HA developer docs, codebase inspection, and quality scale rules)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Entity Platforms (Layer 5)                 │
│  ┌────────┐  ┌──────┐  ┌───────┐  ┌──────┐  ┌──────────┐  │
│  │ sensor │  │switch│  │climate│  │number│  │select/bin│  │
│  └───┬────┘  └──┬───┘  └───┬───┘  └──┬───┘  └────┬─────┘  │
│      │          │          │         │            │        │
├──────┴──────────┴──────────┴─────────┴────────────┴────────┤
│              VitotrolEntity (Layer 4: entity.py)            │
│   CoordinatorEntity + optimistic updates + attr lifecycle   │
├─────────────────────────────────────────────────────────────┤
│           VitotrolCoordinator (Layer 3: coordinator.py)     │
│   DataUpdateCoordinator + write ops + re-auth + polling     │
├─────────────────────────────────────────────────────────────┤
│                VitotrolAPI (Layer 2: api.py)                 │
│   SOAP client + async wait pattern + session management     │
├─────────────────────────────────────────────────────────────┤
│                Constants (Layer 1: const.py)                 │
│   + attributes.py (registry) + strings.json (translations)  │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | What Needs Changing |
|-----------|----------------|---------------------|
| `__init__.py` | Entry setup, API creation, coordinator init, platform forwarding | Use `ConfigEntryAuthFailed` for login failures (not just `ConfigEntryNotReady`). Pass `config_entry` to coordinator constructor. |
| `config_flow.py` | Credential validation, reauth, options flow | Already solid. Add `reconfigure` step (Gold tier). Consider `async_step_reconfigure` for changing username. |
| `coordinator.py` | Polling orchestration, write delegation, re-auth retry | Add `ConfigEntryAuthFailed` raise on persistent auth failure. Add optimistic rollback on write failure. |
| `entity.py` | Base entity class, lifecycle, data access, optimistic updates | Add `_update_coordinator_data` rollback support. |
| `switch.py` | On/off control with optimistic state | Wrap write in try/except; raise `HomeAssistantError` on failure. |
| `number.py` | Numeric setpoint control | Raise `ServiceValidationError` for out-of-range values. Raise `HomeAssistantError` on write failure. |
| `climate.py` | Composite entity with multi-attr writes | Check `writable` flag before writing presets (RO guard). Raise `HomeAssistantError` on failure. |
| `select.py` | Enum selection control | Raise `HomeAssistantError` on write failure. |
| `diagnostics.py` | Debug data export | Add attribute catalog to diagnostics output. |
| `strings.json` | UI text for config flow and entities | Already good. Add `reconfigure` step strings if implementing. |

## Architectural Patterns

### Pattern 1: ConfigEntryAuthFailed for Automatic Reauth Triggering

**What:** When the coordinator detects persistent authentication failure (login fails after retry), raise `ConfigEntryAuthFailed` instead of `UpdateFailed`. HA automatically puts the config entry in failure state and starts a reauth flow, showing a notification to the user.

**When to use:** In `_async_update_data()` when re-login fails. In `async_setup_entry()` when initial login returns auth error.

**Trade-offs:** Provides proper UX (user sees "Reauthentication required" in UI) instead of generic "Update failed" errors. The integration already has a reauth flow (`async_step_reauth` / `async_step_reauth_confirm`), so this just wires it up correctly.

**Current gap:** The integration raises `ConfigEntryNotReady` for all setup failures and `UpdateFailed` for all polling failures. Auth failures should be distinguished.

**Example:**
```python
# In __init__.py async_setup_entry:
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

try:
    await api.login()
    devices = await api.get_devices()
except VitotrolAuthError as err:
    raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
except VitotrolError as err:
    raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

# In coordinator.py _async_update_data:
from homeassistant.exceptions import ConfigEntryAuthFailed

except VitotrolAuthError as err:
    try:
        await self.api.login()
        return await self._do_update()
    except VitotrolAuthError as retry_err:
        raise ConfigEntryAuthFailed(
            f"Authentication failed after retry: {retry_err}"
        ) from retry_err
```

**Confidence:** HIGH -- documented at [HA Developer Docs: Handling Setup Failures](https://developers.home-assistant.io/docs/integration_setup_failures/)

### Pattern 2: Action Exceptions (HomeAssistantError / ServiceValidationError)

**What:** Entity write operations (service actions) must raise `HomeAssistantError` when the device/service is unreachable, and `ServiceValidationError` when the input is invalid. These exceptions propagate to the UI as user-visible error messages.

**When to use:** In every entity method that performs a write: `async_turn_on`, `async_turn_off`, `async_set_native_value`, `async_set_temperature`, `async_set_hvac_mode`, `async_set_preset_mode`.

**Trade-offs:** Adds try/except blocks to every write method, but provides proper error feedback to users instead of silent failures or generic exceptions.

**Current gap:** Write operations propagate raw `VitotrolError` / `VitotrolAuthError` exceptions. These are not HA-recognized exception types, so the UI shows a generic "An error occurred" message. The optimistic state update happens before the write, so on failure the entity shows wrong state.

**Example:**
```python
from homeassistant.exceptions import HomeAssistantError

async def async_turn_on(self, **kwargs: Any) -> None:
    """Turn on the switch."""
    try:
        await self.coordinator.async_write(
            self._device, self._vitotrol_attr_id, "1"
        )
    except (VitotrolError, VitotrolAuthError) as err:
        raise HomeAssistantError(
            f"Failed to turn on {self._attr_name}: {err}"
        ) from err
    # Only update optimistically AFTER successful write
    self._update_coordinator_data(self._vitotrol_attr_id, "1")
    self.async_write_ha_state()
```

**Confidence:** HIGH -- documented at [HA Quality Scale: action-exceptions](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-exceptions/)

### Pattern 3: Optimistic Update with Rollback on Failure

**What:** Update the coordinator data store immediately for responsive UI, but revert to the previous value if the write fails. This is a refinement of the current pattern which updates optimistically but never rolls back.

**When to use:** All write operations where the API is slow (4-15 seconds).

**Trade-offs:** With Pattern 2 (action exceptions), the approach shifts: do the write first, update optimistically only on success. This is simpler and more correct than write-then-rollback. The Vitotrol API write takes ~4s, which is acceptable for a loading spinner in the UI.

**Recommended approach:** Move optimistic update AFTER the await, not before. This eliminates the rollback problem entirely because the optimistic update only happens on success.

**Current gap:** The current code updates coordinator data AFTER the write await, but if the write raises an exception, the optimistic update is skipped (which is correct for the switch). However, for climate presets, multiple writes are sequential and partial failure leaves inconsistent state.

**Actually, looking at the code more carefully:** The switch does `await write` then `_update_coordinator_data` then `async_write_ha_state`. If the write raises, the optimistic update is never applied -- which is the correct pattern. The real issue is that exceptions from writes are not caught and translated to `HomeAssistantError`. The climate entity is the exception: partial writes in `async_set_preset_mode` can leave inconsistent optimistic state.

**Example for climate preset fix:**
```python
async def async_set_preset_mode(self, preset_mode: str) -> None:
    """Set preset mode with atomic rollback on partial failure."""
    eco_attr = self._cfg.eco_mode_attr
    party_attr = self._cfg.party_mode_attr

    # Snapshot current state for rollback
    snapshot: dict[int, str | None] = {}
    writes_done: list[tuple[int, str]] = []

    try:
        if preset_mode == PRESET_ECO and eco_attr is not None:
            if party_attr is not None and self._get_attr_value(party_attr) == "1":
                snapshot[party_attr] = self._get_attr_value(party_attr)
                await self.coordinator.async_write(self._device, party_attr, "0")
                writes_done.append((party_attr, "0"))
            snapshot[eco_attr] = self._get_attr_value(eco_attr)
            await self.coordinator.async_write(self._device, eco_attr, "1")
            writes_done.append((eco_attr, "1"))
        # ... other modes ...
    except (VitotrolError, VitotrolAuthError) as err:
        raise HomeAssistantError(
            f"Failed to set preset {preset_mode}: {err}"
        ) from err

    # Only apply optimistic updates after all writes succeed
    for attr_id, value in writes_done:
        self._update_coordinator_data(attr_id, value)
    self.async_write_ha_state()
```

**Confidence:** HIGH for the pattern; MEDIUM for climate-specific implementation (needs testing against real API behavior)

### Pattern 4: Coordinator Config Entry Integration

**What:** Pass the `config_entry` to the `DataUpdateCoordinator` constructor so HA can properly associate the coordinator with the config entry lifecycle. This enables `async_config_entry_first_refresh()` to work correctly and allows `ConfigEntryAuthFailed` raised from `_async_update_data` to automatically trigger reauth.

**When to use:** Always. Required for Silver tier.

**Current gap:** The coordinator constructor does not receive `config_entry`. It works because `async_config_entry_first_refresh()` is called externally, but passing `config_entry` enables HA to automatically handle coordinator lifecycle (e.g., cancelling update timers on unload).

**Example:**
```python
# coordinator.py
class VitotrolCoordinator(DataUpdateCoordinator[VitotrolData]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,  # <-- add this
        api: VitotrolAPI,
        devices: list[VitotrolDevice],
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,  # <-- pass to parent
            update_interval=timedelta(seconds=scan_interval),
        )
```

**Confidence:** HIGH -- this is standard HA coordinator pattern per [architecture discussion #1073](https://github.com/home-assistant/architecture/discussions/1073)

### Pattern 5: Entity Availability via Coordinator State

**What:** Entities become unavailable when the coordinator fails to update (e.g., API is down). `CoordinatorEntity` handles this automatically via its `available` property. The integration correctly extends this with attribute-level availability checks.

**Current state:** Already implemented correctly. Each entity overrides `available` to check both `super().available` (coordinator is healthy) AND `self._vitotrol_attr_id in self._device_data` (attribute was returned by API). This is the correct HA pattern.

**No changes needed** for basic availability. The integration handles this well.

**Confidence:** HIGH

### Pattern 6: Writable Attribute RO Guard

**What:** Before writing to an attribute, check the `writable` flag from the attribute catalog. This prevents writes to read-only attributes that would fail silently or crash the API.

**When to use:** In `coordinator.async_write()` as a pre-flight check, and specifically in `climate.py` for eco/party mode attributes that may be RO on some devices.

**Current gap:** The climate entity writes to `eco_mode_attr` and `party_mode_attr` without checking if they are writable. On devices where these are RO, the write fails silently (error caught in coordinator, logged, but optimistic state was already applied -- though per Pattern 2 this would be fixed by moving optimistic updates after writes).

**Example:**
```python
# coordinator.py
async def async_write(self, device, attr_id, value):
    catalog = self._attribute_catalog.get(device.device_id, {})
    info = catalog.get(attr_id)
    if info and not info.writable:
        raise ServiceValidationError(
            f"Attribute {attr_id} ({info.name}) is read-only"
        )
    # ... proceed with write
```

**Confidence:** HIGH -- directly addresses a known bug documented in CONCERNS.md

## Data Flow

### Write Flow (Current vs. Recommended)

```
CURRENT:
  User Action → entity.async_turn_on()
    → await coordinator.async_write(device, attr_id, value)
    → _update_coordinator_data(attr_id, value)    # optimistic
    → async_write_ha_state()                       # push to UI
    (if write fails: exception propagates as unhandled VitotrolError)

RECOMMENDED:
  User Action → entity.async_turn_on()
    → try:
    →   await coordinator.async_write(device, attr_id, value)
    → except VitotrolError:
    →   raise HomeAssistantError(...)              # user sees error in UI
    → _update_coordinator_data(attr_id, value)     # only on success
    → async_write_ha_state()                       # push confirmed state
```

### Auth Failure Flow (Current vs. Recommended)

```
CURRENT:
  Coordinator poll → _async_update_data()
    → VitotrolAuthError → re-login → retry
    → still fails → raise UpdateFailed  # generic, no reauth prompt

RECOMMENDED:
  Coordinator poll → _async_update_data()
    → VitotrolAuthError → re-login → retry
    → still fails → raise ConfigEntryAuthFailed  # triggers reauth flow
    → HA shows "Reauthentication required" notification
    → User clicks → async_step_reauth → enters new password → reload
```

### Setup Flow (Current vs. Recommended)

```
CURRENT:
  async_setup_entry()
    → api.login() fails → ConfigEntryNotReady (even for bad password)
    → HA retries every 5 min forever (wrong for auth errors)

RECOMMENDED:
  async_setup_entry()
    → api.login() fails with VitotrolAuthError → ConfigEntryAuthFailed
    → HA triggers reauth flow immediately (correct for auth errors)
    → api.login() fails with VitotrolError → ConfigEntryNotReady
    → HA retries with backoff (correct for network errors)
```

## Anti-Patterns

### Anti-Pattern 1: Treating Auth Errors as Transient Failures

**What people do:** Raise `ConfigEntryNotReady` or `UpdateFailed` for authentication errors, causing HA to retry forever with wrong credentials.
**Why it is wrong:** The user never sees a reauth prompt. The integration silently retries with wrong credentials every 5 minutes, generating log noise and wasting API calls.
**Do this instead:** Raise `ConfigEntryAuthFailed` for auth errors. This immediately surfaces the issue to the user and stops wasteful retries.

### Anti-Pattern 2: Optimistic Updates Before Confirming the Write

**What people do:** Update entity state immediately, then await the write, hoping it succeeds.
**Why it is wrong:** If the write fails, the UI shows incorrect state until the next coordinator refresh (up to 300s later). Users think the action succeeded when it did not.
**Do this instead:** Await the write first, then update optimistically only on success. If the write fails, raise `HomeAssistantError` so the UI shows an error toast. The 4-second write delay is acceptable -- the UI shows a loading spinner.

### Anti-Pattern 3: Swallowing Write Errors Silently

**What people do:** Catch exceptions in write paths and only log them, without propagating to the entity or user.
**Why it is wrong:** The user has no feedback that their action failed. They may retry multiple times, potentially queuing conflicting writes.
**Do this instead:** Let write exceptions propagate as `HomeAssistantError`. HA shows a red error toast in the UI. The entity state stays at the last confirmed value.

### Anti-Pattern 4: Writing to Read-Only Attributes

**What people do:** Assume all attributes discovered in the catalog are writable because they are exposed as interactive entities.
**Why it is wrong:** The SOAP API returns an error for writes to RO attributes, but the error may be generic (not "attribute is read-only"). Combined with optimistic updates, the entity shows a state that was never actually written.
**Do this instead:** Check `AttributeTypeInfo.writable` before sending a write. Raise `ServiceValidationError` if the attribute is RO.

## Integration Points

### External Services

| Service | Integration Pattern | Gotchas |
|---------|---------------------|---------|
| Viessmann SOAP API | aiohttp via `async_get_clientsession(hass)` | Single session per account. Cookie-based auth. No concurrent sessions. |
| HA Entity Registry | `er.async_get(hass)` for pre-seeding | Must match entity unique_id format exactly. |
| HA Config Entry | `entry.runtime_data` for storing coordinator | Must pass `config_entry` to coordinator for proper lifecycle. |

### Internal Boundaries

| Boundary | Communication | What Needs Changing |
|----------|---------------|---------------------|
| `api.py` <-> `coordinator.py` | Direct method calls, exception types | No change needed. Exception hierarchy is clean. |
| `coordinator.py` <-> entity platforms | `coordinator.data` dict + `async_write()` | Add RO guard in `async_write()`. |
| `entity.py` <-> platforms | Inheritance + `_update_coordinator_data()` | No structural change. Write patterns updated in platforms. |
| `config_flow.py` <-> `__init__.py` | Config entry data dict | No change needed. |
| `__init__.py` <-> HA | `ConfigEntryNotReady` / `ConfigEntryAuthFailed` | Distinguish auth vs. connectivity errors. |

## HA Quality Scale Alignment

The integration currently meets **Bronze** tier. The following changes are needed for **Silver**:

| Silver Rule | Current Status | What to Change |
|-------------|----------------|----------------|
| `action-exceptions` | Not done -- raw exceptions propagate | Wrap writes in try/except, raise `HomeAssistantError` / `ServiceValidationError` |
| `reauthentication-flow` | Partially done -- flow exists but not triggered automatically | Raise `ConfigEntryAuthFailed` in setup and coordinator to trigger reauth flow |
| `entity-unavailable` | Done -- entities check attr presence + coordinator health | No change needed |
| `parallel-updates` | Done -- `PARALLEL_UPDATES = 0` on all platforms | No change needed |
| `config-entry-unloading` | Done -- `async_unload_entry` unloads platforms | No change needed |
| `appropriate-polling` | Done -- configurable scan interval with options flow | No change needed |
| `log-when-unavailable` | Partially done -- coordinator logs errors | Ensure consistent WARNING level for user-relevant failures |

Additional **Gold** tier aspirations:

| Gold Rule | Current Status | What to Change |
|-----------|----------------|----------------|
| `diagnostics` | Done -- basic diagnostics with redaction | Add attribute catalog dump to diagnostics |
| `reconfigure-flow` | Not done | Add `async_step_reconfigure` for changing username |
| `entity-translations` | Partially done -- known entities have translations | Ensure all entity names use `translation_key` |
| `test-coverage` | Partially done -- good but gaps exist | Fill gaps: optimistic rollback, malformed enums, concurrent writes |

## Suggested Build Order

Based on dependency analysis and risk:

1. **Coordinator config_entry integration** (Pattern 4) -- Foundational. 5 minutes. Enables all other patterns.
2. **ConfigEntryAuthFailed in setup** (Pattern 1, setup path) -- Fixes the most visible UX issue. 15 minutes.
3. **ConfigEntryAuthFailed in coordinator** (Pattern 1, polling path) -- Completes auth error handling. 15 minutes.
4. **Action exceptions in write paths** (Pattern 2) -- All six entity platforms. 45 minutes.
5. **RO guard in coordinator.async_write** (Pattern 6) -- Prevents silent write failures. 10 minutes.
6. **Climate preset atomic writes** (Pattern 3) -- Most complex write path. 30 minutes.
7. **Diagnostics enhancement** -- Add attribute catalog. 15 minutes.
8. **Test coverage for new patterns** -- Tests for auth flows, action exceptions, RO guard. 2 hours.

**Rationale:** Steps 1-3 are foundational HA patterns that should be done first because they affect the integration lifecycle. Steps 4-6 are entity-level improvements that can be done in any order. Step 7 is independent. Step 8 should follow all code changes.

## Sources

- [HA Developer Docs: Handling Setup Failures](https://developers.home-assistant.io/docs/integration_setup_failures/) -- `ConfigEntryNotReady`, `ConfigEntryAuthFailed` patterns (HIGH confidence)
- [HA Quality Scale: action-exceptions](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-exceptions/) -- `HomeAssistantError` / `ServiceValidationError` rule (HIGH confidence)
- [HA Quality Scale: reauthentication-flow](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow/) -- Reauth flow requirements (HIGH confidence)
- [HA Developer Docs: Config Flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/) -- Config flow best practices (HIGH confidence)
- [HA Architecture Discussion #1073](https://github.com/home-assistant/architecture/discussions/1073) -- Coordinator setup patterns (MEDIUM confidence)
- [HA Integration Quality Scale Overview](https://developers.home-assistant.io/docs/core/integration-quality-scale/) -- Tier requirements (HIGH confidence)
- [Peblar coordinator reauth PR](https://github.com/home-assistant/core/pull/162919) -- Silent re-login pattern example (MEDIUM confidence)
- Codebase inspection of `custom_components/vitotrol/` -- Current implementation analysis (HIGH confidence)

---
*Architecture research for: Vitotrol HASS HA best practices*
*Researched: 2026-03-04*
