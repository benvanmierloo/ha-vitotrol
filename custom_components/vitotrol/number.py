"""Number platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import AttributeTypeInfo, VitotrolDevice
from .attributes import ATTRIBUTE_REGISTRY, AttrMeta
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitotrolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vitotrol number entities."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[NumberEntity] = []

    for device in coordinator.devices:
        catalog = coordinator.get_attribute_catalog(device.device_id)

        for attr_id, info in catalog.items():
            meta = ATTRIBUTE_REGISTRY.get(attr_id)

            if meta is not None:
                if meta.platform != "number":
                    continue
                entities.append(VitotrolNumber(coordinator, device, info, meta))
            else:
                # Unknown attr: auto-route RW numeric non-enum to number
                if not info.writable or not info.readable:
                    continue
                if info.enum_values is not None:
                    continue
                entities.append(VitotrolNumber(coordinator, device, info, meta=None))

    async_add_entities(entities)


class VitotrolNumber(VitotrolEntity, NumberEntity):
    """Number entity for a writable Vitotrol attribute."""

    _attr_mode = NumberMode.BOX
    _attr_suggested_display_precision = 0

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

        if meta is not None:
            self._attr_name = meta.name
            self._attr_entity_registry_enabled_default = meta.enabled_by_default
            self._attr_native_unit_of_measurement = meta.unit
            self._attr_device_class = meta.device_class
            self._attr_entity_category = meta.entity_category
        else:
            self._attr_name = info.name
            self._attr_entity_registry_enabled_default = False
            if info.unit == "\u00b0C":
                self._attr_device_class = NumberDeviceClass.TEMPERATURE
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            elif info.unit:
                self._attr_native_unit_of_measurement = info.unit

        # Min/max from API metadata
        try:
            self._attr_native_min_value = float(info.min_value)
        except (ValueError, TypeError):
            pass
        try:
            self._attr_native_max_value = float(info.max_value)
        except (ValueError, TypeError):
            pass

        # The API only accepts whole numbers for writable attributes.
        self._attr_native_step = 1.0

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._vitotrol_attr_id in self._device_data

    @property
    def native_value(self) -> int | None:
        """Return the current value."""
        raw = self._get_attr_value(self._vitotrol_attr_id)
        if raw is None:
            return None
        try:
            return int(float(raw))
        except (ValueError, OverflowError):
            _LOGGER.debug(
                "Number %s (attr %d): cannot parse %r as number",
                self._attr_name,
                self._vitotrol_attr_id,
                raw,
            )
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        str_value = str(int(value))
        await self.coordinator.async_write(
            self._device, self._vitotrol_attr_id, str_value
        )
        self._update_coordinator_data(self._vitotrol_attr_id, str_value)
        self.async_write_ha_state()
