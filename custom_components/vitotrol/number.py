"""Number platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import AttributeTypeInfo, VitotrolDevice
from .attributes import ATTRIBUTE_REGISTRY, AttrMeta
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity, entity_key_for_attr, infer_unknown_metadata

PARALLEL_UPDATES = 0

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
                inferred = infer_unknown_metadata(info)
                if inferred.platform != "number":
                    continue
                entities.append(VitotrolNumber(coordinator, device, info, meta=None))

    async_add_entities(entities)


class VitotrolNumber(VitotrolEntity, NumberEntity):
    """Number entity for a writable Vitotrol attribute."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        info: AttributeTypeInfo,
        meta: AttrMeta | None,
    ) -> None:
        key = entity_key_for_attr(info.attr_id, meta)
        super().__init__(coordinator, device, key)
        self._vitotrol_attr_id = info.attr_id

        if meta is not None:
            self._attr_name = meta.name
            self._attr_entity_registry_enabled_default = meta.enabled_by_default
            self._attr_native_unit_of_measurement = meta.unit
            self._attr_device_class = meta.device_class
            self._attr_entity_category = meta.entity_category
        else:
            inferred = infer_unknown_metadata(info)
            self._attr_name = inferred.display_name
            self._attr_entity_registry_enabled_default = False

        # Min/max from API metadata
        try:
            self._attr_native_min_value = float(info.min_value)
        except (ValueError, TypeError):
            pass
        try:
            self._attr_native_max_value = float(info.max_value)
        except (ValueError, TypeError):
            pass

        # Store type for use in native_value and async_set_native_value
        self._info_type = info.type

        # Step size and display precision from attribute type
        if info.type == "Double":
            self._attr_native_step = 0.5
            self._attr_suggested_display_precision = 1
        else:
            self._attr_native_step = 1.0
            self._attr_suggested_display_precision = 0

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._vitotrol_attr_id in self._device_data

    @property
    def native_value(self) -> float | int | None:
        """Return the current value."""
        raw = self._get_attr_value(self._vitotrol_attr_id)
        if raw is None:
            return None
        try:
            v = float(raw)
            return v if self._info_type == "Double" else int(v)
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
        # Format: Double attrs can have meaningful decimals; Integer attrs must be whole
        str_value = str(value) if self._info_type == "Double" else str(int(value))
        old_value = self._get_attr_value(self._vitotrol_attr_id)
        try:
            await self.coordinator.async_write(
                self._device, self._vitotrol_attr_id, str_value
            )
        except Exception as err:
            if old_value is not None:
                self._update_coordinator_data(self._vitotrol_attr_id, old_value)
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Failed to write {self._attr_name} (attr {self._vitotrol_attr_id}): {err}"
            ) from err
        self._update_coordinator_data(self._vitotrol_attr_id, str_value)
        self.async_write_ha_state()
