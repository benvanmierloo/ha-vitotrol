"""Tests for switch platform."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vitotrol.api import AttributeTypeInfo
from .conftest import FAKE_DEVICE


# Attr 7855 — Party mode (enabled by default, switch platform)
FAKE_PARTY_MODE_INFO = AttributeTypeInfo(
    attr_id=7855,
    name="Party_Betrieb",
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
    enum_values=None,
)


async def _load(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_party_mode_off(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Switch reports off when the raw value is '0'."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={7855: FAKE_PARTY_MODE_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={7855: "0"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("switch.vitovalor_300_p_party_mode")
    assert state is not None, (
        f"Entity not found. States: {[s.entity_id for s in hass.states.async_all()]}"
    )
    assert state.state == "off"


async def test_turn_off_writes_value(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Turning the switch off calls write_data_wait with '0' and updates state."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={7855: FAKE_PARTY_MODE_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={7855: "1"})

    await _load(hass, mock_config_entry)

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.vitovalor_300_p_party_mode"},
        blocking=True,
    )

    mock_api.return_value.write_data_wait.assert_called_once_with(FAKE_DEVICE, 7855, "0")

    state = hass.states.get("switch.vitovalor_300_p_party_mode")
    assert state.state == "off"


async def test_turn_on_writes_value(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Turning the switch on calls write_data_wait with '1' and updates state."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={7855: FAKE_PARTY_MODE_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={7855: "0"})

    await _load(hass, mock_config_entry)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.vitovalor_300_p_party_mode"},
        blocking=True,
    )

    mock_api.return_value.write_data_wait.assert_called_once_with(FAKE_DEVICE, 7855, "1")

    state = hass.states.get("switch.vitovalor_300_p_party_mode")
    assert state.state == "on"


async def test_unknown_binary_switch_registered(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """An unknown binary writable ENUM attr is registered as a disabled switch."""
    unknown_info = AttributeTypeInfo(
        attr_id=99801,
        name="Unknown_Switch_Attr",
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
    mock_api.return_value.get_type_info = AsyncMock(return_value={99801: unknown_info})
    mock_api.return_value.get_data = AsyncMock(return_value={99801: "0"})

    await _load(hass, mock_config_entry)

    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.entity_registry import RegistryEntryDisabler
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("switch", "vitotrol", "1001_attr_99801")
    assert entity_id is not None
    entry = ent_reg.async_get(entity_id)
    assert entry.disabled_by == RegistryEntryDisabler.INTEGRATION


async def test_turn_on_rollback_on_write_failure(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """When async_turn_on raises, entity state reverts to old value ('off') and HomeAssistantError is raised."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={7855: FAKE_PARTY_MODE_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={7855: "0"})
    mock_api.return_value.write_data_wait = AsyncMock(side_effect=Exception("SOAP fault"))

    await _load(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.vitovalor_300_p_party_mode"},
            blocking=True,
        )

    state = hass.states.get("switch.vitovalor_300_p_party_mode")
    assert state.state == "off", f"Expected 'off' after rollback, got {state.state!r}"


async def test_turn_off_rollback_on_write_failure(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """When async_turn_off raises, entity state reverts to old value ('on') and HomeAssistantError is raised."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={7855: FAKE_PARTY_MODE_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={7855: "1"})
    mock_api.return_value.write_data_wait = AsyncMock(side_effect=Exception("SOAP fault"))

    await _load(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.vitovalor_300_p_party_mode"},
            blocking=True,
        )

    state = hass.states.get("switch.vitovalor_300_p_party_mode")
    assert state.state == "on", f"Expected 'on' after rollback, got {state.state!r}"
