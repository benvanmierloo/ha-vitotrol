"""Tests for integration setup and teardown."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vitotrol.api import VitotrolError
from custom_components.vitotrol.const import DOMAIN

from .conftest import FAKE_ATTR_INFO, FAKE_DEVICE


async def _setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Helper: add entry to hass and load the integration."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_entry_success(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Integration loads successfully with valid credentials and a device."""
    await _setup_entry(hass, mock_config_entry)

    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_setup_entry_auth_failure_raises_not_ready(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Auth failure during setup → entry goes to SETUP_RETRY state."""
    mock_api.return_value.login = AsyncMock(side_effect=VitotrolError("network"))
    await _setup_entry(hass, mock_config_entry)

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Unloading the entry succeeds and leaves HA clean."""
    await _setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
