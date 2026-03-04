"""Tests for number platform."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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


# ---------------------------------------------------------------------------
# Step size from attribute type (BUGS-03)
# ---------------------------------------------------------------------------

FAKE_INTEGER_SETPOINT_INFO = AttributeTypeInfo(
    attr_id=82,
    name="TempNormBetrieb",
    type="Integer",
    type_value="2",
    min_value="10",
    max_value="30",
    unit="°C",
    group="Heizkreis",
    heating_circuit_id=None,
    factory_default=None,
    readable=True,
    writable=True,
    enum_values=None,
)


async def test_double_attr_has_step_0_5(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Double-type number entity has native_step=0.5 and suggested_display_precision=1."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={51: FAKE_HW_SETPOINT_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={51: "55.0"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("number.vitovalor_300_p_hot_water_setpoint_temperature")
    assert state is not None
    assert float(state.attributes["step"]) == 0.5


async def test_integer_attr_has_step_1_0(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Integer-type number entity has native_step=1.0."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={82: FAKE_INTEGER_SETPOINT_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={82: "21"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("number.vitovalor_300_p_heat_normal_temperature")
    assert state is not None
    assert float(state.attributes["step"]) == 1.0


async def test_double_native_value_returns_float(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Double-type number entity returns float native_value (not int-truncated)."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={51: FAKE_HW_SETPOINT_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={51: "20.5"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("number.vitovalor_300_p_hot_water_setpoint_temperature")
    assert state is not None
    # State string for a float should include decimal representation
    assert state.state == "20.5"


async def test_integer_native_value_returns_int(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Integer-type number entity returns int native_value (no .0 suffix)."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={82: FAKE_INTEGER_SETPOINT_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={82: "21"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("number.vitovalor_300_p_heat_normal_temperature")
    assert state is not None
    assert state.state == "21"


async def test_set_value_rollback_on_write_failure(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """async_set_native_value raises HomeAssistantError and reverts state on write failure."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={51: FAKE_HW_SETPOINT_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={51: "50.0"})
    mock_api.return_value.write_data_wait = AsyncMock(side_effect=Exception("SOAP fault"))

    await _load(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": "number.vitovalor_300_p_hot_water_setpoint_temperature",
                "value": 55.0,
            },
            blocking=True,
        )

    state = hass.states.get("number.vitovalor_300_p_hot_water_setpoint_temperature")
    assert state.state == "50.0", f"Expected '50.0' after rollback, got {state.state!r}"
