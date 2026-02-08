"""Select platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import AttributeTypeInfo, VitotrolDevice
from .const import KNOWN_ATTR_IDS
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitotrolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vitotrol select entities for writable enum attributes."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[SelectEntity] = []

    for device in coordinator.devices:
        catalog = coordinator.get_attribute_catalog(device.device_id)

        for attr_id, info in catalog.items():
            if attr_id in KNOWN_ATTR_IDS:
                continue
            if not info.writable or not info.readable:
                continue
            if info.enum_values is None:
                continue

            entities.append(
                VitotrolDynamicSelect(coordinator, device, info)
            )

    async_add_entities(entities)


class VitotrolDynamicSelect(VitotrolEntity, SelectEntity):
    """Select entity for a dynamically discovered writable enum attribute."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        info: AttributeTypeInfo,
    ) -> None:
        super().__init__(coordinator, device, f"attr_{info.attr_id}")
        self._attr_id = info.attr_id
        self._attr_name = info.name

        # Build forward (raw -> label) and reverse (label -> raw) mappings
        self._value_to_label = {str(k): v for k, v in info.enum_values.items()}
        self._label_to_value = {v: str(k) for k, v in info.enum_values.items()}
        self._attr_options = list(self._value_to_label.values())

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._attr_id in self._device_data

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        raw = self._get_attr_value(self._attr_id)
        if raw is None:
            return None
        return self._value_to_label.get(raw)

    async def async_select_option(self, option: str) -> None:
        """Set a new option."""
        raw_value = self._label_to_value.get(option)
        if raw_value is None:
            return

        await self.coordinator.async_write(
            self._device, self._attr_id, raw_value
        )
        self._update_coordinator_data(self._attr_id, raw_value)
        self.async_write_ha_state()
