"""The Viessmann Vitotrol integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VitotrolAPI, VitotrolError
from .const import (
    CONF_CUSTOM_ATTRIBUTES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import VitotrolCoordinator

_LOGGER = logging.getLogger(__name__)

type VitotrolConfigEntry = ConfigEntry[VitotrolRuntimeData]


class VitotrolRuntimeData:
    """Runtime data stored in hass.data for a config entry."""

    def __init__(
        self,
        api: VitotrolAPI,
        coordinator: VitotrolCoordinator,
    ) -> None:
        self.api = api
        self.coordinator = coordinator


async def async_setup_entry(hass: HomeAssistant, entry: VitotrolConfigEntry) -> bool:
    """Set up Vitotrol from a config entry."""
    session = async_get_clientsession(hass)
    api = VitotrolAPI(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    try:
        await api.login()
        devices = await api.get_devices()
    except VitotrolError as err:
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = VitotrolCoordinator(hass, api, devices, scan_interval)

    # Apply custom attributes from options
    _apply_custom_attrs(coordinator, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = VitotrolRuntimeData(api=api, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: VitotrolConfigEntry
) -> bool:
    """Unload a Vitotrol config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant, entry: VitotrolConfigEntry
) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


def _apply_custom_attrs(
    coordinator: VitotrolCoordinator, entry: ConfigEntry
) -> None:
    """Set custom attribute IDs on the coordinator from entry options."""
    custom_list = entry.options.get(CONF_CUSTOM_ATTRIBUTES, [])
    attr_ids = [c["attr_id"] for c in custom_list if "attr_id" in c]
    coordinator.set_custom_attr_ids(attr_ids)
