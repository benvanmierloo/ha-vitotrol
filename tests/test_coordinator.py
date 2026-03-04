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


async def test_refresh_failure_falls_back_to_get_data(hass: HomeAssistant) -> None:
    """If refresh_data_wait fails, coordinator still calls get_data (cached values)."""
    api = AsyncMock()
    api.refresh_data_wait = AsyncMock(side_effect=VitotrolError("timeout"))
    api.get_data = AsyncMock(return_value={5373: "10.0"})

    coord = _make_coordinator(hass, api)
    _seed_coordinator(coord)

    data = await coord._async_update_data()

    # Despite refresh failure, get_data was still called
    api.get_data.assert_called_once()
    assert data[FAKE_DEVICE.device_id][5373] == "10.0"


async def test_write_auth_error_triggers_relogin(hass: HomeAssistant) -> None:
    """On VitotrolAuthError during write, coordinator re-logs in and retries."""
    api = AsyncMock()
    api.login = AsyncMock()
    api.write_data_wait = AsyncMock(
        side_effect=[VitotrolAuthError("expired"), None]
    )

    coord = _make_coordinator(hass, api)

    await coord.async_write(FAKE_DEVICE, 7855, "1")

    assert api.login.call_count == 1
    assert api.write_data_wait.call_count == 2


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


async def test_auth_error_retry_also_fails(hass: HomeAssistant) -> None:
    """If re-login succeeds but the retry also fails, UpdateFailed is raised."""
    api = AsyncMock()
    api.login = AsyncMock()
    api.refresh_data_wait = AsyncMock(return_value=None)
    api.get_data = AsyncMock(
        side_effect=[VitotrolAuthError("expired"), VitotrolError("still broken")]
    )

    coord = _make_coordinator(hass, api)
    _seed_coordinator(coord)

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()

    assert api.login.call_count == 1


def test_pre_seed_skips_empty_catalog(hass: HomeAssistant) -> None:
    """pre_seed_from_registry skips devices whose attribute catalog is empty."""
    api = AsyncMock()
    coord = _make_coordinator(hass, api)
    # No catalog populated → empty

    class _FakeEntry:
        disabled = False
        unique_id = "1001_outdoor_temperature"

    coord.pre_seed_from_registry([_FakeEntry()])
    assert FAKE_DEVICE.device_id not in coord._entity_attr_ids


def test_pre_seed_skips_disabled_registry_entries(hass: HomeAssistant) -> None:
    """pre_seed_from_registry skips disabled entity registry entries."""
    api = AsyncMock()
    coord = _make_coordinator(hass, api)
    coord._attribute_catalog[FAKE_DEVICE.device_id] = {5373: FAKE_ATTR_INFO}

    class _DisabledEntry:
        disabled = True
        unique_id = "1001_outdoor_temperature"

    coord.pre_seed_from_registry([_DisabledEntry()])
    assert not coord._entity_attr_ids.get(FAKE_DEVICE.device_id)


async def test_debug_catalog_logged(hass: HomeAssistant, caplog) -> None:
    """_log_attribute_catalog is called and logs JSON when DEBUG is enabled."""
    import logging
    from custom_components.vitotrol.api import AttributeTypeInfo

    enum_attr = AttributeTypeInfo(
        attr_id=92,
        name="Betriebs_Art",
        type="ENUM",
        type_value="1",
        min_value=None,
        max_value=None,
        unit=None,
        group="Allgemein",
        heating_circuit_id=None,
        factory_default=None,
        readable=True,
        writable=True,
        enum_values={0: "Aus", 1: "Ein"},
    )

    api = AsyncMock()
    api.get_type_info = AsyncMock(
        return_value={5373: FAKE_ATTR_INFO, 92: enum_attr}
    )

    coord = _make_coordinator(hass, api)

    with caplog.at_level(logging.DEBUG, logger="custom_components.vitotrol.coordinator"):
        await coord.async_setup_type_info()

    assert "Attribute catalog for" in caplog.text
    assert "Vitovalor 300-P" in caplog.text
