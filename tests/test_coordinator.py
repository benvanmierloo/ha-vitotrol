"""Tests for VitotrolCoordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.vitotrol.api import VitotrolAuthError, VitotrolError
from custom_components.vitotrol.coordinator import VitotrolCoordinator

from .conftest import FAKE_ATTR_INFO, FAKE_DEVICE


def _make_coordinator(hass: HomeAssistant, api) -> VitotrolCoordinator:
    """Build a coordinator with a fake device list."""
    return VitotrolCoordinator(hass, api, [FAKE_DEVICE], scan_interval=300)


def _seed_coordinator(coord: VitotrolCoordinator) -> None:
    """Pre-populate coordinator with the single fake attribute."""
    coord._attribute_catalog[FAKE_DEVICE.device_id] = {5373: FAKE_ATTR_INFO}
    coord._entity_attr_ids[FAKE_DEVICE.device_id] = {"uid_5373": {5373}}


async def test_successful_update(hass: HomeAssistant) -> None:
    """Coordinator returns data on a clean refresh."""
    api = AsyncMock()
    api.refresh_data_wait = AsyncMock(return_value=None)
    api.get_data = AsyncMock(return_value={5373: "12.5"})

    coord = _make_coordinator(hass, api)
    _seed_coordinator(coord)

    data = await coord._async_update_data()

    assert data[FAKE_DEVICE.device_id][5373] == "12.5"


async def test_auth_error_triggers_relogin_and_succeeds(hass: HomeAssistant) -> None:
    """On VitotrolAuthError the coordinator re-logs in and retries."""
    api = AsyncMock()
    api.login = AsyncMock()
    api.refresh_data_wait = AsyncMock(return_value=None)
    api.get_data = AsyncMock(
        side_effect=[VitotrolAuthError("expired"), {5373: "11.0"}]
    )

    coord = _make_coordinator(hass, api)
    _seed_coordinator(coord)

    data = await coord._async_update_data()

    assert api.login.call_count == 1
    assert data[FAKE_DEVICE.device_id][5373] == "11.0"


async def test_persistent_error_raises_update_failed(hass: HomeAssistant) -> None:
    """If the retry also fails, UpdateFailed is raised (marks coordinator unavailable)."""
    api = AsyncMock()
    api.login = AsyncMock()
    api.refresh_data_wait = AsyncMock(return_value=None)
    api.get_data = AsyncMock(side_effect=VitotrolError("timeout"))

    coord = _make_coordinator(hass, api)
    _seed_coordinator(coord)

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
