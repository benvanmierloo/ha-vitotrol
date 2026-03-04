"""Tests for diagnostics."""
from __future__ import annotations

from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry


async def _load(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_redacts_credentials(
    hass: HomeAssistant, hass_client, mock_api, mock_config_entry
) -> None:
    """Diagnostics output must not expose the real password or username."""
    await _load(hass, mock_config_entry)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert diag["config_entry_data"][CONF_PASSWORD] == "**REDACTED**"
    assert diag["config_entry_data"][CONF_USERNAME] == "**REDACTED**"


async def test_diagnostics_includes_device_info(
    hass: HomeAssistant, hass_client, mock_api, mock_config_entry
) -> None:
    """Diagnostics output includes device list from the coordinator."""
    await _load(hass, mock_config_entry)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert len(diag["devices"]) == 1
    assert diag["devices"][0]["device_name"] == "Vitovalor 300-P"
