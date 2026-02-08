"""Base entity for the Viessmann Vitotrol integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import VitotrolDevice
from .const import DOMAIN
from .coordinator import VitotrolCoordinator


class VitotrolEntity(CoordinatorEntity[VitotrolCoordinator]):
    """Base class for all Vitotrol entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._device_id = device.device_id
        self._attr_unique_id = f"{device.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.device_id))},
            name=device.device_name,
            manufacturer="Viessmann",
            model="Vitotrol",
            configuration_url=(
                "https://vitotrolapp.viessmann-climatesolutions.com"
            ),
        )

    @property
    def _device_data(self) -> dict[int, str]:
        """Return the data dict for this entity's device."""
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.get(self._device_id, {})

    def _get_attr_value(self, attr_id: int) -> str | None:
        """Return a raw attribute value string, or None if unavailable."""
        return self._device_data.get(attr_id)

    def _update_coordinator_data(self, attr_id: int, value: str) -> None:
        """Optimistically update a value in the coordinator data store.

        Mutates coordinator.data directly so that property-based state
        reads pick up the new value immediately.
        """
        if self.coordinator.data is None:
            return
        device_data = self.coordinator.data.get(self._device_id)
        if device_data is None:
            return
        device_data[attr_id] = value
