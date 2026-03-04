"""Tests for sensor platform."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import FAKE_DEVICE


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


async def test_sensor_unavailable_when_coordinator_has_no_data(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Sensor is unavailable when the coordinator data is missing the attribute."""
    mock_api.return_value.get_data = AsyncMock(return_value={})

    await _load(hass, mock_config_entry)

    state = hass.states.get("sensor.vitovalor_300_p_outdoor_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
