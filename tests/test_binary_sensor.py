"""Tests for binary_sensor platform."""
from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vitotrol.api import AttributeTypeInfo


# Attr 600 — Burner (enabled by default, running device class, on_values=("1",))
FAKE_BURNER_INFO = AttributeTypeInfo(
    attr_id=600,
    name="Brenner_Status",
    type="ENUM",
    type_value="1",
    min_value=None,
    max_value=None,
    unit=None,
    group="Allgemein",
    heating_circuit_id=None,
    factory_default=None,
    readable=True,
    writable=False,
    enum_values=None,
)


async def _load(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_burner_on(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Binary sensor reports on when the burner fires."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={600: FAKE_BURNER_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={600: "1"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.vitovalor_300_p_burner")
    assert state is not None, (
        f"Entity not found. States: {[s.entity_id for s in hass.states.async_all()]}"
    )
    assert state.state == "on"


async def test_unknown_binary_attr_inferred_from_enum(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """An unknown ENUM binary attr (Aus/Ein) is inferred as a binary_sensor."""
    from custom_components.vitotrol.api import AttributeTypeInfo
    unknown_info = AttributeTypeInfo(
        attr_id=99998,
        name="Custom_Binary",
        type="ENUM",
        type_value="1",
        min_value=None,
        max_value=None,
        unit=None,
        group="Allgemein",
        heating_circuit_id=None,
        factory_default=None,
        readable=True,
        writable=False,
        enum_values={0: "Aus", 1: "Ein"},
    )
    mock_api.return_value.get_type_info = AsyncMock(return_value={99998: unknown_info})
    mock_api.return_value.get_data = AsyncMock(return_value={99998: "1"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("sensor.vitovalor_300_p_custom_binary")
    # Unknown binary sensors without a matched registry entry are inferred as binary_sensor
    # but disabled by default — check it's registered via entity registry instead
    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("binary_sensor.vitovalor_300_p_custom_binary")
    assert entry is not None, (
        f"binary_sensor not found. All entities: {[e.entity_id for e in ent_reg.entities.values()]}"
    )


async def test_burner_off(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Binary sensor reports off when the burner is idle."""
    mock_api.return_value.get_type_info = AsyncMock(return_value={600: FAKE_BURNER_INFO})
    mock_api.return_value.get_data = AsyncMock(return_value={600: "0"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.vitovalor_300_p_burner")
    assert state is not None
    assert state.state == "off"
