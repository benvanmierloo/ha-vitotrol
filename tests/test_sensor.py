"""Tests for sensor platform."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vitotrol.api import AttributeTypeInfo
from .conftest import FAKE_DEVICE


# Attr 708 — Current operating mode (enabled, enum sensor with enum_map in registry)
FAKE_OPERATING_MODE_STATUS_INFO = AttributeTypeInfo(
    attr_id=708,
    name="Betriebsart_Ist",
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

# Unknown attr (not in ATTRIBUTE_REGISTRY) with type="Double", readable/writable
FAKE_UNKNOWN_SENSOR_INFO = AttributeTypeInfo(
    attr_id=99999,
    name="Custom_Attr",
    type="Double",
    type_value="3",
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


async def test_outdoor_temp_sensor_value(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Outdoor temperature sensor reflects coordinator data."""
    await _load(hass, mock_config_entry)

    state = hass.states.get("sensor.vitovalor_300_p_outdoor_temperature")
    assert state is not None, (
        f"Entity not found. Available states: {[s.entity_id for s in hass.states.async_all()]}"
    )
    assert state.state == "12.5"


async def test_enum_sensor_returns_label(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Enum sensor maps raw value to its English label via enum_map."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={708: FAKE_OPERATING_MODE_STATUS_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={708: "2"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("sensor.vitovalor_300_p_current_operating_mode")
    assert state is not None, (
        f"Entity not found. States: {[s.entity_id for s in hass.states.async_all()]}"
    )
    assert state.state == "Normal"


async def test_unknown_sensor_attr_in_registry(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """An unknown Double read-only attr is inferred as a sensor and registered (disabled)."""
    mock_api.return_value.get_type_info = AsyncMock(
        return_value={99999: FAKE_UNKNOWN_SENSOR_INFO}
    )
    mock_api.return_value.get_data = AsyncMock(return_value={99999: "42.0"})

    await _load(hass, mock_config_entry)

    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("sensor.vitovalor_300_p_custom_attr")
    assert entry is not None, (
        f"Unknown sensor not in entity registry. "
        f"All: {[e.entity_id for e in ent_reg.entities.values()]}"
    )


async def test_sensor_unavailable_when_coordinator_has_no_data(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Sensor is unavailable when the coordinator data is missing the attribute."""
    mock_api.return_value.get_data = AsyncMock(return_value={})

    await _load(hass, mock_config_entry)

    state = hass.states.get("sensor.vitovalor_300_p_outdoor_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_unknown_enum_sensor_registered(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """An unknown readonly multi-value ENUM attr is registered as a disabled sensor."""
    unknown_info = AttributeTypeInfo(
        attr_id=99804,
        name="Unknown_Enum_Sensor",
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
        enum_values={0: "Alpha", 1: "Beta", 2: "Gamma"},
    )
    mock_api.return_value.get_type_info = AsyncMock(return_value={99804: unknown_info})
    mock_api.return_value.get_data = AsyncMock(return_value={99804: "1"})

    await _load(hass, mock_config_entry)

    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.entity_registry import RegistryEntryDisabler
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", "vitotrol", "1001_attr_99804")
    assert entity_id is not None
    entry = ent_reg.async_get(entity_id)
    assert entry.disabled_by == RegistryEntryDisabler.INTEGRATION


async def test_sensor_invalid_numeric_data_unknown(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """A numeric sensor with non-parseable data reports unknown state."""
    from homeassistant.const import STATE_UNKNOWN
    mock_api.return_value.get_data = AsyncMock(return_value={5373: "bad_value"})

    await _load(hass, mock_config_entry)

    state = hass.states.get("sensor.vitovalor_300_p_outdoor_temperature")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_date_sensor_returns_raw_string(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """A Date-type sensor (no state_class, no enum) returns the raw string value."""
    date_info = AttributeTypeInfo(
        attr_id=99805,
        name="Some_Date_Attr",
        type="Date",
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
    mock_api.return_value.get_type_info = AsyncMock(return_value={99805: date_info})
    mock_api.return_value.get_data = AsyncMock(return_value={99805: "2024-01-15"})

    await _load(hass, mock_config_entry)

    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.entity_registry import RegistryEntryDisabler
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", "vitotrol", "1001_attr_99805")
    assert entity_id is not None
    # Enable and reload to get the state
    ent_reg.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "2024-01-15"
