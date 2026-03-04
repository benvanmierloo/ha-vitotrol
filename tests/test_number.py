"""Tests for number platform."""
from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vitotrol.api import AttributeTypeInfo
from .conftest import FAKE_DEVICE


# Attr 51 — Hot water setpoint temperature (enabled by default, num_temp category)
FAKE_HW_SETPOINT_INFO = AttributeTypeInfo(
    attr_id=51,
    name="WW_Soll",
    type="Double",
    type_value="3",
    min_value="10",
    max_value="60",
    unit="°C",
    group="Warmwasser",
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


async def test_hot_water_setpoint_value(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Number entity reports the current setpoint value."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={51: FAKE_HW_SETPOINT_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={51: "55"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("number.vitovalor_300_p_hot_water_setpoint_temperature")
    assert state is not None, (
        f"Entity not found. States: {[s.entity_id for s in hass.states.async_all()]}"
    )
    assert state.state == "55"


async def test_number_unavailable_when_attr_missing(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Number entity is unavailable when coordinator data lacks the attribute."""
    from homeassistant.const import STATE_UNAVAILABLE
    mock_api.return_value.get_type_info = AsyncMock(return_value={51: FAKE_HW_SETPOINT_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={})

    await _load(hass, mock_config_entry)

    state = hass.states.get("number.vitovalor_300_p_hot_water_setpoint_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_set_value_writes_integer(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Setting a value writes the integer string to the API."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={51: FAKE_HW_SETPOINT_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={51: "50"})

    await _load(hass, mock_config_entry)

    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.vitovalor_300_p_hot_water_setpoint_temperature",
            "value": 55.0,
        },
        blocking=True,
    )

    mock_api.return_value.write_data_wait.assert_called_once_with(FAKE_DEVICE, 51, "55")


async def test_unknown_number_attr_registered(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """An unknown writable Double attr (meta=None) is registered as a disabled number."""
    unknown_info = AttributeTypeInfo(
        attr_id=99803,
        name="Unknown_Number_Attr",
        type="Double",
        type_value="3",
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
    mock_api.return_value.get_type_info = AsyncMock(return_value={99803: unknown_info})
    mock_api.return_value.get_data = AsyncMock(return_value={99803: "42"})

    await _load(hass, mock_config_entry)

    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.entity_registry import RegistryEntryDisabler
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("number", "vitotrol", "1001_attr_99803")
    assert entity_id is not None
    entry = ent_reg.async_get(entity_id)
    assert entry.disabled_by == RegistryEntryDisabler.INTEGRATION


async def test_number_invalid_data_state_unknown(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Number entity reports unknown state when value is non-numeric."""
    from homeassistant.const import STATE_UNKNOWN
    mock_api.return_value.get_type_info = AsyncMock(return_value={51: FAKE_HW_SETPOINT_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={51: "abc"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("number.vitovalor_300_p_hot_water_setpoint_temperature")
    assert state is not None
    assert state.state == STATE_UNKNOWN
