"""Select platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
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
    """Set up Vitotrol select entities for writable enum attributes."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[SelectEntity] = []

    for device in coordinator.devices:
        catalog = coordinator.get_attribute_catalog(device.device_id)

        for attr_id, info in catalog.items():
            meta = ATTRIBUTE_REGISTRY.get(attr_id)

            if meta is not None:
                if meta.platform != "select":
                    continue
                entities.append(VitotrolSelect(coordinator, device, info, meta))
            else:
                # Unknown attr: auto-route RW enum to select
                if not info.writable or not info.readable:
                    continue
                if info.enum_values is None:
                    continue
                entities.append(VitotrolSelect(coordinator, device, info, meta=None))

    async_add_entities(entities)


class VitotrolSelect(VitotrolEntity, SelectEntity):
    """Select entity for a writable enum attribute."""

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

        if meta is not None and meta.enum_map is not None:
            self._attr_name = meta.name
            self._attr_entity_registry_enabled_default = meta.enabled_by_default
            self._value_to_label = meta.enum_map
        else:
            # Fallback: use German labels from GetTypeInfo
            self._attr_name = info.name if meta is None else meta.name
            self._attr_entity_registry_enabled_default = (
                meta.enabled_by_default if meta else False
            )
            self._value_to_label = (
                {str(k): v for k, v in info.enum_values.items()}
                if info.enum_values
                else {}
            )

        self._label_to_value = {v: k for k, v in self._value_to_label.items()}
        self._attr_options = list(self._value_to_label.values())

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._vitotrol_attr_id in self._device_data

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        raw = self._get_attr_value(self._vitotrol_attr_id)
        if raw is None:
            return None
        return self._value_to_label.get(raw)

    async def async_select_option(self, option: str) -> None:
        """Set a new option."""
        raw_value = self._label_to_value.get(option)
        if raw_value is None:
            return

        await self.coordinator.async_write(
            self._device, self._vitotrol_attr_id, raw_value
        )
        self._update_coordinator_data(self._vitotrol_attr_id, raw_value)
        self.async_write_ha_state()
