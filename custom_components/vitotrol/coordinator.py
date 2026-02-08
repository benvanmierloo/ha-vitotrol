"""DataUpdateCoordinator for the Viessmann Vitotrol integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AttributeTypeInfo, VitotrolAPI, VitotrolAuthError, VitotrolDevice, VitotrolError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, KNOWN_ATTR_IDS

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
        # Per-device attribute catalog from GetTypeInfo: {device_id: {attr_id: info}}
        self._attribute_catalog: dict[int, dict[int, AttributeTypeInfo]] = {}
        # Per-entity attr_id registrations: {device_id: {entity_uid: {attr_ids}}}
        self._entity_attr_ids: dict[int, dict[str, set[int]]] = {}

    def get_attribute_catalog(
        self, device_id: int
    ) -> dict[int, AttributeTypeInfo]:
        """Return the attribute catalog for a device."""
        return self._attribute_catalog.get(device_id, {})

    async def async_setup_type_info(self) -> None:
        """Discover all device attributes via GetTypeInfo.

        Must be called before the first data refresh.
        """
        for device in self.devices:
            catalog = await self.api.get_type_info(device)
            self._attribute_catalog[device.device_id] = catalog
            _LOGGER.info(
                "Discovered %d attributes for %s",
                len(catalog),
                device.device_name,
            )

    # ------------------------------------------------------------------
    # Entity attr_id registration — only registered attrs get polled
    # ------------------------------------------------------------------

    def register_entity_attrs(
        self, device_id: int, entity_uid: str, attr_ids: set[int]
    ) -> None:
        """Register attr_ids that an entity needs polled."""
        self._entity_attr_ids.setdefault(device_id, {})[entity_uid] = attr_ids

    def unregister_entity_attrs(
        self, device_id: int, entity_uid: str
    ) -> None:
        """Unregister an entity's attr_ids."""
        device_entities = self._entity_attr_ids.get(device_id)
        if device_entities:
            device_entities.pop(entity_uid, None)

    def _get_attr_ids(self, device_id: int) -> list[int]:
        """Return attr_ids to poll: union of all registered entity needs.

        Before entity setup (first refresh), falls back to KNOWN_ATTR_IDS
        that the device actually supports.
        """
        device_entities = self._entity_attr_ids.get(device_id, {})
        if device_entities:
            result: set[int] = set()
            for attr_ids in device_entities.values():
                result.update(attr_ids)
            return list(result)

        # Fallback for first refresh before entities are registered
        catalog = self._attribute_catalog.get(device_id, {})
        return [
            attr_id
            for attr_id in KNOWN_ATTR_IDS
            if attr_id in catalog and catalog[attr_id].readable
        ]

    # ------------------------------------------------------------------

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
                _LOGGER.debug("No attr_ids to poll for %s", device.device_name)
                result[did] = {}
                continue

            catalog = self._attribute_catalog.get(did, {})
            attr_names = [
                f"{aid}:{catalog[aid].name}" if aid in catalog else str(aid)
                for aid in sorted(attr_ids)
            ]
            _LOGGER.debug(
                "Polling %s: %d attrs [%s]",
                device.device_name,
                len(attr_ids),
                ", ".join(attr_names),
            )

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
