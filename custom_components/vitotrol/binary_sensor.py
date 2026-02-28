"""Binary sensor platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import AttributeTypeInfo, VitotrolDevice
from .attributes import ATTRIBUTE_REGISTRY, AttrMeta
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity, entity_key_for_attr


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitotrolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vitotrol binary sensor entities."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[BinarySensorEntity] = []

    for device in coordinator.devices:
        catalog = coordinator.get_attribute_catalog(device.device_id)

        for attr_id, info in catalog.items():
            meta = ATTRIBUTE_REGISTRY.get(attr_id)
            if meta is None or meta.platform != "binary_sensor":
                continue
            entities.append(VitotrolBinarySensor(coordinator, device, info, meta))

    async_add_entities(entities)


class VitotrolBinarySensor(VitotrolEntity, BinarySensorEntity):
    """Binary sensor entity for a Vitotrol status attribute."""

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        info: AttributeTypeInfo,
        meta: AttrMeta,
    ) -> None:
        key = entity_key_for_attr(info.attr_id, meta)
        super().__init__(coordinator, device, key)
        self._vitotrol_attr_id = info.attr_id
        self._on_values = meta.on_values or ("1",)
        self._attr_name = meta.name
        self._attr_entity_registry_enabled_default = meta.enabled_by_default
        self._attr_device_class = meta.device_class

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._vitotrol_attr_id in self._device_data

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        raw = self._get_attr_value(self._vitotrol_attr_id)
        if raw is None:
            return None
        return raw in self._on_values
