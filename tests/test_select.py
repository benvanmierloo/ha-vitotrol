"""Tests for select platform."""
from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vitotrol.api import AttributeTypeInfo
from .conftest import FAKE_DEVICE


# Attr 92 — Operating mode (disabled by default, select platform)
# Has enum_map in ATTRIBUTE_REGISTRY: {"0": "Off", "1": "DHW only", "2": "Heating + DHW", ...}
FAKE_OPERATING_MODE_INFO = AttributeTypeInfo(
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
    enum_values=None,
)


async def _load(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_select_disabled_by_default(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Operating mode select entity is created but disabled by default."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2"})

    await _load(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get("select.vitovalor_300_p_operating_mode")
    assert entity_entry is not None, "Select entity not in entity registry"
    assert entity_entry.disabled_by == RegistryEntryDisabler.INTEGRATION


async def test_select_state_after_enable(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """After enabling the select entity and reloading, state reflects coordinator data."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2"})

    await _load(hass, mock_config_entry)

    # Enable the disabled-by-default entity
    ent_reg = er.async_get(hass)
    ent_reg.async_update_entity(
        "select.vitovalor_300_p_operating_mode", disabled_by=None
    )

    # Reload the config entry so the coordinator pre-seeds attr 92 and entity gets state
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.vitovalor_300_p_operating_mode")
    assert state is not None, (
        f"Select entity not in states after enable+reload. "
        f"States: {[s.entity_id for s in hass.states.async_all()]}"
    )
    assert state.state == "Heating + DHW"


async def test_select_option_writes_value(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Selecting an option calls write_data_wait with the corresponding raw value."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2"})

    await _load(hass, mock_config_entry)

    # Enable the entity and reload before calling the service
    ent_reg = er.async_get(hass)
    ent_reg.async_update_entity(
        "select.vitovalor_300_p_operating_mode", disabled_by=None
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_api.return_value.write_data_wait.reset_mock()

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.vitovalor_300_p_operating_mode",
            "option": "Off",
        },
        blocking=True,
    )

    mock_api.return_value.write_data_wait.assert_called_once_with(FAKE_DEVICE, 92, "0")


async def test_unknown_multi_select_registered(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """An unknown multi-value writable ENUM attr is registered as a disabled select."""
    unknown_info = AttributeTypeInfo(
        attr_id=99802,
        name="Unknown_Select_Attr",
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
        enum_values={0: "Alpha", 1: "Beta", 2: "Gamma"},
    )
    mock_api.return_value.get_type_info = AsyncMock(return_value={99802: unknown_info})
    mock_api.return_value.get_data = AsyncMock(return_value={99802: "0"})

    await _load(hass, mock_config_entry)

    from homeassistant.helpers.entity_registry import RegistryEntryDisabler
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("select", "vitotrol", "1001_attr_99802")
    assert entity_id is not None
    entry = ent_reg.async_get(entity_id)
    assert entry.disabled_by == RegistryEntryDisabler.INTEGRATION
