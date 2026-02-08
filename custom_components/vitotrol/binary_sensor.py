"""Binary sensor platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import VitotrolDevice
from .const import (
    ATTR_BURNER_STATE,
    ATTR_CIRCULATION_PUMP_STATE,
    ATTR_FROST_PROTECTION_STATUS,
    ATTR_HEATING_PUMP_STATUS,
    ATTR_HOLIDAYS_STATUS,
    ATTR_INTERNAL_PUMP_STATUS,
)
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity


@dataclass(frozen=True, kw_only=True)
class VitotrolBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Vitotrol binary sensor entity."""

    attr_id: int
    on_values: tuple[str, ...] = ("1",)


BINARY_SENSOR_DESCRIPTIONS: tuple[VitotrolBinarySensorEntityDescription, ...] = (
    VitotrolBinarySensorEntityDescription(
        key="burner",
        translation_key="burner",
        attr_id=ATTR_BURNER_STATE,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    VitotrolBinarySensorEntityDescription(
        key="internal_pump",
        translation_key="internal_pump",
        attr_id=ATTR_INTERNAL_PUMP_STATUS,
        device_class=BinarySensorDeviceClass.RUNNING,
        on_values=("1", "3"),
    ),
    VitotrolBinarySensorEntityDescription(
        key="heating_pump",
        translation_key="heating_pump",
        attr_id=ATTR_HEATING_PUMP_STATUS,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    VitotrolBinarySensorEntityDescription(
        key="circulation_pump",
        translation_key="circulation_pump",
        attr_id=ATTR_CIRCULATION_PUMP_STATE,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    VitotrolBinarySensorEntityDescription(
        key="frost_protection",
        translation_key="frost_protection",
        attr_id=ATTR_FROST_PROTECTION_STATUS,
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    VitotrolBinarySensorEntityDescription(
        key="holiday_mode",
        translation_key="holiday_mode",
        attr_id=ATTR_HOLIDAYS_STATUS,
    ),
)


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
        for desc in BINARY_SENSOR_DESCRIPTIONS:
            if desc.attr_id in catalog:
                entities.append(
                    VitotrolBinarySensor(coordinator, device, desc)
                )

    async_add_entities(entities)


class VitotrolBinarySensor(VitotrolEntity, BinarySensorEntity):
    """Binary sensor entity for a Vitotrol status attribute."""

    entity_description: VitotrolBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        description: VitotrolBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, device, description.key)
        self.entity_description = description
        self._attr_id = description.attr_id

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._attr_id in self._device_data

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        raw = self._get_attr_value(self._attr_id)
        if raw is None:
            return None
        return raw in self.entity_description.on_values
