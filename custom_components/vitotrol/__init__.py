"""The Viessmann Vitotrol integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VitotrolAPI, VitotrolError
from .const import (
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
    coordinator = VitotrolCoordinator(hass, api, devices, scan_interval, config_entry=entry)

    # Discover all device attributes via GetTypeInfo
    try:
        await coordinator.async_setup_type_info()
    except VitotrolError as err:
        raise ConfigEntryNotReady(
            f"Failed to discover device attributes: {err}"
        ) from err

    # Pre-seed coordinator with entity registrations from the HA entity
    # registry so the first refresh polls the right set of attributes
    # (not just the enabled-by-default fallback).
    entity_reg = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_reg, entry.entry_id
    )
    coordinator.pre_seed_from_registry(registry_entries)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = VitotrolRuntimeData(api=api, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: VitotrolConfigEntry
) -> bool:
    """Unload a Vitotrol config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
