# Coding Conventions

**Analysis Date:** 2025-03-04

## Naming Patterns

**Files:**
- Lowercase with underscores: `api.py`, `coordinator.py`, `config_flow.py`
- Platform files named after their HA platform: `sensor.py`, `binary_sensor.py`, `switch.py`, `climate.py`, `number.py`, `select.py`
- Test files mirror source with `test_` prefix: `test_api.py`, `test_coordinator.py`, `test_sensor.py`

**Functions:**
- Async functions: `async_setup_entry()`, `async_login()`, `async_get_data()`
- Sync functions: snake_case, private functions prefixed with single underscore: `_xml_escape()`, `_find_text()`, `_strip_ns()`
- Private module-level functions use underscore prefix: `_log_attribute_catalog()`, `_is_binary_enum()`, `_infer_numeric_meta()`
- Property methods use `@property` decorator: `native_value`, `available`, `is_on`

**Variables:**
- Instance variables prefixed with underscore for private: `self._cookies`, `self._password`, `self._attribute_catalog`
- HA attributes use underscore prefix: `_attr_unique_id`, `_attr_name`, `_attr_device_info`
- Constants in UPPERCASE: `DEFAULT_SCAN_INTERVAL`, `API_ENDPOINT`, `PARALLEL_UPDATES`
- Dictionaries for lookup tables: `base_entries`, `enum_values`, `data`

**Classes:**
- PascalCase: `VitotrolAPI`, `VitotrolCoordinator`, `VitotrolEntity`, `VitotrolSensor`
- Exception classes inherit from `VitotrolError`: `VitotrolAuthError`, `VitotrolError`
- Dataclasses use PascalCase: `VitotrolDevice`, `AttributeTypeInfo`, `AttrMeta`, `ClimateMeta`

## Code Style

**Formatting:**
- Line length: typical Python convention (Black defaults, around 88 characters implicit)
- No external formatter detected (no .flake8, .prettierrc, or pyproject.toml linting config visible)
- Docstrings: Google-style with description, args, and return types
- Module docstrings document purpose and dependencies

**Linting:**
- No pre-commit hooks detected
- Code appears to follow standard Python practices without explicit linter enforcement
- Use of `from __future__ import annotations` in all files for forward references

**Import order:**
1. Standard library imports (`asyncio`, `logging`, `re`, `json`, `dataclasses`)
2. Third-party imports (`aiohttp`, `homeassistant.*`, `pytest`)
3. Local imports (`.api`, `.const`, `.coordinator`, etc.)
4. Blank line between each group

**Example from `sensor.py`:**
```python
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import AttributeTypeInfo, VitotrolDevice
from .attributes import ATTRIBUTE_REGISTRY, AttrMeta
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity, entity_key_for_attr, infer_unknown_metadata
```

## Error Handling

**Patterns:**
- Exception hierarchy: `VitotrolError` (base) → `VitotrolAuthError` (specific)
- Errors logged before re-raising (e.g., `_LOGGER.warning("Authentication failed: %s", err)`)
- Config flow catches `VitotrolAuthError`, `VitotrolError`, `aiohttp.ClientError` separately
- Coordinator wraps errors in `UpdateFailed` for HA framework consistency
- API errors trigger coordinator re-login via `VitotrolAuthError` catch in `_async_update_data()`

**Example from `config_flow.py`:**
```python
try:
    await api.login()
    devices = await api.get_devices()
except VitotrolAuthError as err:
    _LOGGER.warning("Authentication failed: %s", err)
    errors["base"] = "invalid_auth"
except (VitotrolError, aiohttp.ClientError) as err:
    _LOGGER.error("Failed to connect to Vitotrol: %s", err)
    errors["base"] = "cannot_connect"
```

**Example from `coordinator.py` (re-login on auth failure):**
```python
async def _async_update_data(self) -> VitotrolData:
    try:
        return await self._do_update()
    except VitotrolAuthError as err:
        _LOGGER.info("Session expired, re-logging in")
        try:
            await self.api.login()
            return await self._do_update()
        except VitotrolError as err:
            raise UpdateFailed(f"Failed to update Vitotrol data: {err}") from err
```

## Logging

**Framework:** Python `logging` module via `_LOGGER = logging.getLogger(__name__)`

**Patterns:**
- DEBUG: operation details, full attribute catalogs (JSON formatted): `_LOGGER.debug("Discovered %d device(s)", len(devices))`
- INFO: setup milestones, session state: `_LOGGER.info("Attribute catalog for %s", device.device_name)`
- WARNING: recoverable errors like auth failures: `_LOGGER.warning("Authentication failed: %s", err)`
- ERROR: fatal/retry conditions: `_LOGGER.error("Failed to connect to Vitotrol: %s", err)`
- Sensitive data (credentials) never logged, only structure and counts logged

**Example from `api.py`:**
```python
_LOGGER.debug("Login successful")
_LOGGER.debug("Discovered %d device(s)", len(devices))
_LOGGER.debug("GetTypeInfo returned %d attributes for device %d", len(base_entries), device.device_id)
```

## Comments

**When to Comment:**
- Complex algorithm explanations (e.g., enum value parsing in `get_type_info()`)
- Non-obvious heuristics (e.g., status code semantics in `_poll_async_status()`)
- Workarounds and known limitations (e.g., "Enum value entry: "92-0" -> attr_id=92, index=0")
- API quirks and constraints (documented in module docstrings, not inline comments)

**JSDoc/TSDoc:**
- All public methods have docstrings with description, args, return type
- Dataclass fields documented inline where non-obvious
- Private methods may have brief one-liner docstrings or context-heavy multi-line docstrings

**Example from `api.py`:**
```python
async def get_type_info(
    self, device: VitotrolDevice
) -> dict[int, AttributeTypeInfo]:
    """Get all available datapoint definitions for a device."""
    # ... implementation ...
```

**Example from coordinator:**
```python
def _log_attribute_catalog(
    device: VitotrolDevice, catalog: dict[int, AttributeTypeInfo]
) -> None:
    """Log the full attribute catalog as JSON at DEBUG level.

    Outputs a single JSON object that users can copy-paste into a GitHub
    issue to share their device's supported attributes.
    """
```

## Function Design

**Size:** 20–50 lines typical; longer functions break into helper methods (e.g., `_do_update()` in coordinator)

**Parameters:**
- Type hints on all parameters and return values
- Keyword-only arguments for clarity: `async def _send_request(self, soap_action: str, body: str, *, store_cookies: bool = False)`
- Dataclasses used for multi-field returns: `VitotrolDevice`, `AttributeTypeInfo`

**Return Values:**
- Explicit return types, no implicit None
- Empty collections `[]` or `{}` for "no results" (not None)
- Optional returns: `str | None`, `dict | None` with None check by caller
- Tuples for multi-value returns with type hints: `tuple[str | None, str | None, str | None, int | None]`

**Example from `entity.py`:**
```python
def _infer_numeric_meta(name: str) -> tuple[str | None, str | None, str | None, int | None]:
    """Return (device_class, unit, state_class, suggested_precision) for a numeric attr name."""
    # ... returns are always a tuple of 4 elements, even if some are None
```

## Module Design

**Exports:**
- Explicit exports via `__all__` not used; public API clear from class/function names
- Private module-level helpers use underscore prefix: `_xml_escape()`, `_find_text_opt()`
- Classes and public functions exposed directly: `VitotrolAPI`, `VitotrolCoordinator`, `VitotrolEntity`

**Barrel Files:**
- `__init__.py` only re-exports integration-level types: `VitotrolConfigEntry`, `VitotrolRuntimeData`
- No deep aggregation; platforms import directly from their dependencies

**Module layering (dependency order from const.py docs):**
```
const.py
  ↓ (imported by)
api.py (pure Python, no HA deps)
  ↓ (imported by)
attributes.py, coordinator.py
  ↓ (imported by)
entity.py
  ↓ (imported by)
config_flow.py, platforms (sensor.py, switch.py, etc.)
  ↓ (imported by)
__init__.py (wires all together)
```

---

*Convention analysis: 2025-03-04*
