"""Sensor platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import AttributeTypeInfo, VitotrolDevice
from .attributes import ATTRIBUTE_REGISTRY, AttrMeta
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity, infer_unknown_metadata

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitotrolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vitotrol sensor entities."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[SensorEntity] = []

    for device in coordinator.devices:
        catalog = coordinator.get_attribute_catalog(device.device_id)

        for attr_id, info in catalog.items():
            meta = ATTRIBUTE_REGISTRY.get(attr_id)

            if meta is not None:
                if meta.platform != "sensor":
                    continue
                entities.append(VitotrolSensor(coordinator, device, info, meta))
            else:
                inferred = infer_unknown_metadata(info)
                if inferred.platform != "sensor":
                    continue
                entities.append(VitotrolSensor(coordinator, device, info, meta=None))

    async_add_entities(entities)


class VitotrolSensor(VitotrolEntity, SensorEntity):
    """Sensor entity for a Vitotrol attribute."""

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        info: AttributeTypeInfo,
        meta: AttrMeta | None,
    ) -> None:
        key = meta.name.lower().replace(" ", "_") if meta else f"attr_{info.attr_id}"
        super().__init__(coordinator, device, key)
        self._vitotrol_attr_id = info.attr_id
        self._enum_values: dict[str, str] | None = None

        if meta is not None:
            self._attr_name = meta.name
            self._attr_entity_registry_enabled_default = meta.enabled_by_default
            self._attr_native_unit_of_measurement = meta.unit
            self._attr_device_class = meta.device_class
            self._attr_state_class = meta.state_class
            self._attr_suggested_display_precision = meta.suggested_precision
            self._attr_entity_category = meta.entity_category
            if meta.enum_map is not None:
                self._enum_values = meta.enum_map
                self._attr_device_class = SensorDeviceClass.ENUM
                self._attr_options = list(meta.enum_map.values())
        else:
            inferred = infer_unknown_metadata(info)
            self._attr_name = inferred.display_name
            self._attr_entity_registry_enabled_default = False
            if info.enum_values is not None:
                enum_map = {str(k): v for k, v in info.enum_values.items()}
                self._enum_values = enum_map
                self._attr_device_class = SensorDeviceClass.ENUM
                self._attr_options = list(enum_map.values())
            else:
                self._attr_device_class = inferred.device_class
                self._attr_state_class = inferred.state_class
                self._attr_native_unit_of_measurement = inferred.unit
                self._attr_suggested_display_precision = inferred.suggested_precision

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._vitotrol_attr_id in self._device_data

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        raw = self._get_attr_value(self._vitotrol_attr_id)
        if raw is None:
            return None

        if self._enum_values is not None:
            return self._enum_values.get(raw, raw)

        if self._attr_state_class is not None:
            try:
                return float(raw)
            except ValueError:
                _LOGGER.debug(
                    "Sensor %s (attr %d): cannot parse %r as float",
                    self._attr_name,
                    self._vitotrol_attr_id,
                    raw,
                )
                return None

        return raw
