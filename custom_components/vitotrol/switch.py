"""Switch platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import AttributeTypeInfo, VitotrolDevice
from .attributes import ATTRIBUTE_REGISTRY, AttrMeta
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitotrolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vitotrol switch entities."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[SwitchEntity] = []

    for device in coordinator.devices:
        catalog = coordinator.get_attribute_catalog(device.device_id)

        for attr_id, info in catalog.items():
            meta = ATTRIBUTE_REGISTRY.get(attr_id)
            if meta is None or meta.platform != "switch":
                continue
            entities.append(VitotrolSwitch(coordinator, device, info, meta))

    async_add_entities(entities)


class VitotrolSwitch(VitotrolEntity, SwitchEntity):
    """Switch entity for a Vitotrol on/off attribute."""

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        info: AttributeTypeInfo,
        meta: AttrMeta,
    ) -> None:
        key = meta.name.lower().replace(" ", "_")
        super().__init__(coordinator, device, key)
        self._vitotrol_attr_id = info.attr_id
        self._attr_name = meta.name
        self._attr_entity_registry_enabled_default = meta.enabled_by_default

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._vitotrol_attr_id in self._device_data

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        raw = self._get_attr_value(self._vitotrol_attr_id)
        if raw is None:
            return None
        return raw == "1"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.async_write(
            self._device, self._vitotrol_attr_id, "1"
        )
        self._update_coordinator_data(self._vitotrol_attr_id, "1")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.async_write(
            self._device, self._vitotrol_attr_id, "0"
        )
        self._update_coordinator_data(self._vitotrol_attr_id, "0")
        self.async_write_ha_state()
