"""The Viessmann Vitotrol integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VitotrolAPI, VitotrolError
from .attributes import ATTRIBUTE_REGISTRY
from .const import (
    CONF_EXCLUDED_ATTRS,
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

    # Apply attribute exclusions discovered during config flow setup
    excluded_attrs = entry.data.get(CONF_EXCLUDED_ATTRS, {})
    if excluded_attrs:
        coordinator.set_excluded_attrs(excluded_attrs)
        for did_str, aids in excluded_attrs.items():
            names = [
                f"{aid}:{ATTRIBUTE_REGISTRY[aid].name}"
                if aid in ATTRIBUTE_REGISTRY
                else str(aid)
                for aid in aids
            ]
            _LOGGER.info(
                "Device %s: loaded %d excluded attribute(s): %s",
                did_str,
                len(aids),
                ", ".join(names),
            )

    # Discover all device attributes via GetTypeInfo
    try:
        await coordinator.async_setup_type_info()
    except VitotrolError as err:
        raise ConfigEntryNotReady(
            f"Failed to discover device attributes: {err}"
        ) from err

    entry.runtime_data = VitotrolRuntimeData(api=api, coordinator=coordinator)

    # Forward to platforms FIRST so entities register their attr_ids,
    # then refresh with the correct poll set.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await coordinator.async_config_entry_first_refresh()

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
