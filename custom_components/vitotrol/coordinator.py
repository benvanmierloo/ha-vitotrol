"""DataUpdateCoordinator for the Viessmann Vitotrol integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AttributeTypeInfo, VitotrolAPI, VitotrolAuthError, VitotrolDevice, VitotrolError
from .attributes import ATTRIBUTE_REGISTRY
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

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
        # Per-device excluded attrs (probed bad during setup)
        self._excluded_attrs: dict[int, set[int]] = {}

    def set_excluded_attrs(self, excluded: dict[str, list[int]]) -> None:
        """Load excluded attr_ids (from config entry data)."""
        self._excluded_attrs = {
            int(did): set(aids) for did, aids in excluded.items()
        }

    def get_attribute_catalog(
        self, device_id: int
    ) -> dict[int, AttributeTypeInfo]:
        """Return the attribute catalog for a device (excluding bad attrs)."""
        catalog = self._attribute_catalog.get(device_id, {})
        excluded = self._excluded_attrs.get(device_id, set())
        if not excluded:
            return catalog
        return {aid: info for aid, info in catalog.items() if aid not in excluded}

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
    # Pre-seed from entity registry (before first refresh)
    # ------------------------------------------------------------------

    def pre_seed_from_registry(
        self, registry_entries: list,
    ) -> None:
        """Pre-populate entity attr registrations from the HA entity registry.

        Called before the first data refresh so that the coordinator polls
        the correct attributes immediately, rather than falling back to
        only the enabled-by-default set.
        """
        from .attributes import CLIMATE_CONFIGS
        from .entity import entity_key_for_attr

        for device in self.devices:
            did = device.device_id
            catalog = self.get_attribute_catalog(did)
            if not catalog:
                continue

            # Build unique_id → attr_ids mapping
            uid_to_attrs: dict[str, set[int]] = {}

            # Regular single-attr entities
            for attr_id in catalog:
                meta = ATTRIBUTE_REGISTRY.get(attr_id)
                key = entity_key_for_attr(attr_id, meta)
                uid_to_attrs[f"{did}_{key}"] = {attr_id}

            # Climate entity (reads multiple attrs)
            for config in CLIMATE_CONFIGS:
                if config.operating_mode_attr not in catalog:
                    continue
                ids = {
                    config.current_temp_attr,
                    config.target_temp_attr,
                    config.operating_mode_attr,
                }
                for opt in (
                    config.current_mode_attr,
                    config.burner_state_attr,
                    config.eco_mode_attr,
                    config.party_mode_attr,
                ):
                    if opt is not None:
                        ids.add(opt)
                uid_to_attrs[f"{did}_climate"] = ids
                break  # only one climate config per device

            # Match enabled registry entries to our mapping
            seeded = 0
            for reg_entry in registry_entries:
                if reg_entry.disabled:
                    continue
                attr_ids = uid_to_attrs.get(reg_entry.unique_id)
                if attr_ids is not None:
                    self.register_entity_attrs(
                        did, reg_entry.unique_id, attr_ids
                    )
                    seeded += 1

            if seeded:
                _LOGGER.debug(
                    "Pre-seeded %d entity registrations for %s "
                    "from entity registry",
                    seeded,
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

        Before entity setup (first refresh), falls back to enabled-by-default
        registry entries that the device actually supports.  Excluded attrs
        (probed bad during setup) are always filtered out.
        """
        excluded = self._excluded_attrs.get(device_id, set())

        device_entities = self._entity_attr_ids.get(device_id, {})
        if device_entities:
            result: set[int] = set()
            for attr_ids in device_entities.values():
                result.update(attr_ids)
            result -= excluded
            return list(result)

        # Fallback for first refresh before entities are registered
        catalog = self._attribute_catalog.get(device_id, {})
        return [
            attr_id
            for attr_id, meta in ATTRIBUTE_REGISTRY.items()
            if meta.enabled_by_default
            and attr_id in catalog
            and catalog[attr_id].readable
            and attr_id not in excluded
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
        except VitotrolAuthError as err:
            _LOGGER.debug("Auth error (%s), re-logging in and retrying", err)
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
            except VitotrolError as err:
                _LOGGER.warning(
                    "RefreshData failed for %s: %s — reading cached data",
                    device.device_name,
                    err,
                )

            data = await self.api.get_data(device, attr_ids)
            result[did] = data

        return result
