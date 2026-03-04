"""Tests for climate platform."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vitotrol.api import AttributeTypeInfo
from .conftest import FAKE_DEVICE


# Attr 92 — Operating mode (required for boiler climate entity creation)
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
    # Climate entity registers its attr IDs during async_added_to_hass (which runs
    # during platform setup, after the first coordinator refresh).  Trigger a second
    # refresh so the coordinator actually polls those attrs and populates the data.
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()


async def test_climate_hvac_mode_and_temperatures(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Climate entity reports correct HVAC mode and temperatures."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(
        return_value={92: "2", 5367: "20.0", 82: "21.0"}
    )

    await _load(hass, mock_config_entry)

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state is not None, (
        f"Climate entity not found. States: {[s.entity_id for s in hass.states.async_all()]}"
    )
    assert state.state == HVACMode.AUTO  # "2" → Heating + DHW → AUTO
    assert state.attributes["current_temperature"] == 20.0
    assert state.attributes["temperature"] == 21.0


async def test_climate_off_mode(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Climate entity reports OFF when operating mode is 0."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "0"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_set_temperature_calls_write(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Setting target temperature calls write_data_wait for attr 82."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(
        return_value={92: "2", 5367: "20.0", 82: "21.0"}
    )

    await _load(hass, mock_config_entry)

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.vitovalor_300_p_heating", "temperature": 22.0},
        blocking=True,
    )

    mock_api.return_value.write_data_wait.assert_called_once_with(FAKE_DEVICE, 82, "22.0")


async def test_set_hvac_mode_calls_write(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Setting HVAC mode calls write_data_wait for attr 92."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2"})

    await _load(hass, mock_config_entry)
    mock_api.return_value.write_data_wait.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.vitovalor_300_p_heating", "hvac_mode": HVACMode.OFF},
        blocking=True,
    )

    mock_api.return_value.write_data_wait.assert_called_once_with(FAKE_DEVICE, 92, "0")


async def test_climate_preset_eco(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Climate entity shows eco preset when energy saving mode is active."""
    from custom_components.vitotrol.api import AttributeTypeInfo

    eco_info = AttributeTypeInfo(
        attr_id=7852,
        name="EnergySpar_Betrieb",
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
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO, 7852: eco_info}
    )
    # eco mode active (7852 = "1")
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2", 7852: "1"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state is not None
    assert state.attributes["preset_mode"] == "eco"


async def test_climate_set_preset_eco(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Setting preset eco calls write_data_wait for energy saving attr."""
    from custom_components.vitotrol.api import AttributeTypeInfo

    eco_info = AttributeTypeInfo(
        attr_id=7852,
        name="EnergySpar_Betrieb",
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
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO, 7852: eco_info}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2", 7852: "0"})

    await _load(hass, mock_config_entry)
    mock_api.return_value.write_data_wait.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.vitovalor_300_p_heating", "preset_mode": "eco"},
        blocking=True,
    )

    mock_api.return_value.write_data_wait.assert_called_with(FAKE_DEVICE, 7852, "1")


async def test_climate_preset_party(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Climate entity shows boost preset when party mode is active."""
    from custom_components.vitotrol.api import AttributeTypeInfo

    party_info = AttributeTypeInfo(
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
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO, 7855: party_info}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2", 7855: "1"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state is not None
    assert state.attributes["preset_mode"] == "boost"


async def test_climate_set_preset_none_clears_eco(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Setting preset none when eco is active calls write to disable eco."""
    from custom_components.vitotrol.api import AttributeTypeInfo

    eco_info = AttributeTypeInfo(
        attr_id=7852,
        name="EnergySpar_Betrieb",
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
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO, 7852: eco_info}
    )
    # eco currently active
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2", 7852: "1"})

    await _load(hass, mock_config_entry)
    mock_api.return_value.write_data_wait.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.vitovalor_300_p_heating", "preset_mode": "none"},
        blocking=True,
    )

    mock_api.return_value.write_data_wait.assert_called_with(FAKE_DEVICE, 7852, "0")


async def test_climate_not_created_without_operating_mode_attr(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Climate entity is not created when attr 92 is absent from the catalog."""
    # Use a catalog that has only the outdoor temp sensor
    from tests.conftest import FAKE_ATTR_INFO
    mock_api.return_value.get_type_info = AsyncMock(return_value={5373: FAKE_ATTR_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={5373: "12.5"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state is None


async def test_climate_target_info_with_invalid_min_max(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Climate entity handles None min/max for target temp attr (TypeError caught)."""
    target_temp_info = AttributeTypeInfo(
        attr_id=82,
        name="TempNormBetrieb",
        type="Double",
        type_value="3",
        min_value=None,
        max_value=None,
        unit="°C",
        group="Allgemein",
        heating_circuit_id=None,
        factory_default=None,
        readable=True,
        writable=True,
        enum_values=None,
    )
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO, 82: target_temp_info}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2", 82: "21.0"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state is not None
    # Falls back to class defaults (3 and 37) because min/max are None
    assert state.attributes["min_temp"] == 3
    assert state.attributes["max_temp"] == 37


async def test_climate_bad_current_temp_returns_none(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Climate returns None for current_temperature when data is non-numeric."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(
        return_value={92: "2", 5367: "bad", 82: "21.0"}
    )

    await _load(hass, mock_config_entry)

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state is not None
    assert state.attributes.get("current_temperature") is None


async def test_climate_bad_target_temp_returns_none(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Climate returns None for target temperature when data is non-numeric."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(
        return_value={92: "2", 5367: "20.0", 82: "bad"}
    )

    await _load(hass, mock_config_entry)

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state is not None
    assert state.attributes.get("temperature") is None


async def test_climate_set_preset_party(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Setting preset boost calls write_data_wait for party mode attr."""
    party_info = AttributeTypeInfo(
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
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO, 7855: party_info}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2", 7855: "0"})

    await _load(hass, mock_config_entry)
    mock_api.return_value.write_data_wait.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.vitovalor_300_p_heating", "preset_mode": "boost"},
        blocking=True,
    )

    mock_api.return_value.write_data_wait.assert_called_with(FAKE_DEVICE, 7855, "1")


async def test_climate_set_preset_party_disables_eco(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Setting preset boost when eco is active first disables eco, then sets party."""
    eco_info = AttributeTypeInfo(
        attr_id=7852,
        name="EnergySpar_Betrieb",
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
    party_info = AttributeTypeInfo(
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
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO, 7852: eco_info, 7855: party_info}
    )
    # eco currently active
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2", 7852: "1", 7855: "0"})

    await _load(hass, mock_config_entry)
    mock_api.return_value.write_data_wait.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.vitovalor_300_p_heating", "preset_mode": "boost"},
        blocking=True,
    )

    # eco disabled first, then party enabled
    calls = mock_api.return_value.write_data_wait.call_args_list
    assert any(c.args == (FAKE_DEVICE, 7852, "0") for c in calls), "eco not disabled"
    assert any(c.args == (FAKE_DEVICE, 7855, "1") for c in calls), "party not enabled"


async def test_climate_set_preset_none_clears_party(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Setting preset none when party is active calls write to disable party."""
    party_info = AttributeTypeInfo(
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
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO, 7855: party_info}
    )
    # party currently active
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2", 7855: "1"})

    await _load(hass, mock_config_entry)
    mock_api.return_value.write_data_wait.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.vitovalor_300_p_heating", "preset_mode": "none"},
        blocking=True,
    )

    mock_api.return_value.write_data_wait.assert_called_with(FAKE_DEVICE, 7855, "0")


# ---------------------------------------------------------------------------
# Rollback + HomeAssistantError tests (BUGS-03 / BUGS-04)
# ---------------------------------------------------------------------------

async def test_set_temperature_rollback_on_failure(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """async_set_temperature raises HomeAssistantError and reverts temp state on failure."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(
        return_value={92: "2", 5367: "20.0", 82: "21.0"}
    )

    await _load(hass, mock_config_entry)
    mock_api.return_value.write_data_wait = AsyncMock(side_effect=Exception("SOAP fault"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": "climate.vitovalor_300_p_heating", "temperature": 22.0},
            blocking=True,
        )

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state.attributes["temperature"] == 21.0, (
        f"Expected temp 21.0 after rollback, got {state.attributes.get('temperature')!r}"
    )


async def test_set_hvac_mode_rollback_on_failure(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """async_set_hvac_mode raises HomeAssistantError and reverts mode on failure."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2"})

    await _load(hass, mock_config_entry)
    mock_api.return_value.write_data_wait = AsyncMock(side_effect=Exception("SOAP fault"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": "climate.vitovalor_300_p_heating", "hvac_mode": HVACMode.OFF},
            blocking=True,
        )

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state.state == HVACMode.AUTO, (
        f"Expected mode to revert to AUTO, got {state.state!r}"
    )


async def test_set_preset_mode_rollback_on_failure(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """async_set_preset_mode raises HomeAssistantError and reverts all attrs on failure."""
    eco_info = AttributeTypeInfo(
        attr_id=7852,
        name="EnergySpar_Betrieb",
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
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO, 7852: eco_info}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2", 7852: "0"})

    await _load(hass, mock_config_entry)
    mock_api.return_value.write_data_wait = AsyncMock(side_effect=Exception("SOAP fault"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {"entity_id": "climate.vitovalor_300_p_heating", "preset_mode": "eco"},
            blocking=True,
        )

    state = hass.states.get("climate.vitovalor_300_p_heating")
    assert state.attributes["preset_mode"] == "none", (
        f"Expected preset_mode to revert to none, got {state.attributes.get('preset_mode')!r}"
    )


async def test_set_preset_mode_skips_readonly_eco(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """async_set_preset_mode skips read-only eco_mode attr with warning log, does not raise."""
    eco_info = AttributeTypeInfo(
        attr_id=7852,
        name="EnergySpar_Betrieb",
        type="ENUM",
        type_value="1",
        min_value=None,
        max_value=None,
        unit=None,
        group="Allgemein",
        heating_circuit_id=None,
        factory_default=None,
        readable=True,
        writable=False,  # read-only!
        enum_values=None,
    )
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={92: FAKE_OPERATING_MODE_INFO, 7852: eco_info}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={92: "2", 7852: "0"})

    await _load(hass, mock_config_entry)
    mock_api.return_value.write_data_wait.reset_mock()

    # Should NOT raise even though eco_mode attr is read-only
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.vitovalor_300_p_heating", "preset_mode": "eco"},
        blocking=True,
    )

    # write_data_wait should NOT be called for the read-only attr
    mock_api.return_value.write_data_wait.assert_not_called()
