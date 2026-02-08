"""DataUpdateCoordinator for the Viessmann Vitotrol integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VitotrolAPI, VitotrolAuthError, VitotrolDevice, VitotrolError
from .const import ALL_READABLE_ATTRIBUTES, DEFAULT_SCAN_INTERVAL, DISCOVERY_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

type VitotrolData = dict[int, dict[int, str]]


class VitotrolCoordinator(DataUpdateCoordinator[VitotrolData]):
    """Coordinator that polls Vitotrol devices on a configurable interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: VitotrolAPI,
        devices: list[VitotrolDevice],
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.devices = devices
        # Per-device supported attribute tracking: {device_id: list[int]}
        self._supported_attrs: dict[int, list[int]] = {}
        self._discovery_done: dict[int, bool] = {}
        # Custom attribute IDs added by the user via options flow
        self._custom_attr_ids: list[int] = []

    def set_custom_attr_ids(self, attr_ids: list[int]) -> None:
        """Update the list of custom attribute IDs to poll."""
        self._custom_attr_ids = list(attr_ids)

    def _get_attr_ids(self, device_id: int) -> list[int]:
        """Return the full list of attribute IDs to poll for a device."""
        known = self._supported_attrs.get(device_id, ALL_READABLE_ATTRIBUTES)
        # Deduplicate while preserving order
        seen: set[int] = set()
        result: list[int] = []
        for aid in known + self._custom_attr_ids:
            if aid not in seen:
                seen.add(aid)
                result.append(aid)
        return result

    async def async_write(
        self,
        device: VitotrolDevice,
        attr_id: int,
        value: str,
    ) -> None:
        """Write a value with re-auth retry on failure."""
        try:
            await self.api.write_data_wait(device, attr_id, value)
        except VitotrolAuthError:
            _LOGGER.debug("Auth error on write, re-logging in and retrying")
            await self.api.login()
            await self.api.write_data_wait(device, attr_id, value)

    async def _async_update_data(self) -> VitotrolData:
        """Fetch data from the Vitotrol API."""
        try:
            return await self._do_update()
        except VitotrolAuthError:
            _LOGGER.debug("Auth error, re-logging in and retrying")
            try:
                await self.api.login()
                return await self._do_update()
            except VitotrolError as err:
                raise UpdateFailed(f"Re-auth failed: {err}") from err
        except VitotrolError as err:
            # Try re-login once for any API error
            _LOGGER.debug("API error (%s), re-logging in and retrying", err)
            try:
                await self.api.login()
                return await self._do_update()
            except VitotrolError as retry_err:
                raise UpdateFailed(
                    f"Update failed after retry: {retry_err}"
                ) from retry_err

    async def _do_update(self) -> VitotrolData:
        """Perform the actual data fetch for all devices."""
        result: VitotrolData = {}

        for device in self.devices:
            did = device.device_id
            attr_ids = self._get_attr_ids(did)

            if not attr_ids:
                result[did] = {}
                continue

            # Attribute discovery on first run
            if not self._discovery_done.get(did, False):
                try:
                    attr_ids = await asyncio.wait_for(
                        self._discover_attributes(device),
                        timeout=DISCOVERY_TIMEOUT,
                    )
                except TimeoutError:
                    _LOGGER.warning(
                        "Attribute discovery timed out for %s, using all known",
                        device.device_name,
                    )
                    attr_ids = list(ALL_READABLE_ATTRIBUTES) + self._custom_attr_ids
                self._discovery_done[did] = True

            try:
                await self.api.refresh_data_wait(device, attr_ids)
            except VitotrolError:
                _LOGGER.warning(
                    "RefreshData failed for %s, reading cached data",
                    device.device_name,
                )

            data = await self.api.get_data(device, attr_ids)
            result[did] = data

        return result

    async def _discover_attributes(
        self, device: VitotrolDevice
    ) -> list[int]:
        """Discover which known attributes the device supports via binary search.

        Stores the result in self._supported_attrs and returns the supported list.
        """
        did = device.device_id
        all_attrs = list(ALL_READABLE_ATTRIBUTES) + self._custom_attr_ids

        _LOGGER.debug(
            "Starting attribute discovery for %s with %d attributes",
            device.device_name,
            len(all_attrs),
        )

        # First try all at once
        try:
            await self.api.refresh_data_wait(device, all_attrs)
            data = await self.api.get_data(device, all_attrs)
            # All worked — keep whichever returned data
            supported = [aid for aid in all_attrs if aid in data]
            self._supported_attrs[did] = supported
            _LOGGER.debug(
                "All attributes accepted for %s (%d returned data)",
                device.device_name,
                len(supported),
            )
            return supported
        except VitotrolError:
            _LOGGER.debug(
                "Full attribute list failed for %s, starting binary search",
                device.device_name,
            )

        # Binary search to find supported attributes
        supported = await self._binary_search_attrs(device, all_attrs)
        self._supported_attrs[did] = supported
        _LOGGER.info(
            "Attribute discovery for %s complete: %d of %d supported",
            device.device_name,
            len(supported),
            len(all_attrs),
        )
        return supported

    async def _binary_search_attrs(
        self, device: VitotrolDevice, attr_ids: list[int]
    ) -> list[int]:
        """Recursively find supported attributes by splitting and testing."""
        if not attr_ids:
            return []

        # Single attribute — test it directly
        if len(attr_ids) == 1:
            try:
                data = await self.api.get_data(device, attr_ids)
                if attr_ids[0] in data:
                    return attr_ids
            except VitotrolError:
                pass
            return []

        # Try the full list
        try:
            data = await self.api.get_data(device, attr_ids)
            return [aid for aid in attr_ids if aid in data]
        except VitotrolError:
            pass

        # Split in half and recurse
        mid = len(attr_ids) // 2
        left = await self._binary_search_attrs(device, attr_ids[:mid])
        right = await self._binary_search_attrs(device, attr_ids[mid:])
        return left + right
