"""Switch platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import VitotrolDevice
from .const import ATTR_ENERGY_SAVING_MODE, ATTR_PARTY_MODE
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity


@dataclass(frozen=True, kw_only=True)
class VitotrolSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Vitotrol switch entity."""

    attr_id: int


SWITCH_DESCRIPTIONS: tuple[VitotrolSwitchEntityDescription, ...] = (
    VitotrolSwitchEntityDescription(
        key="party_mode",
        translation_key="party_mode",
        attr_id=ATTR_PARTY_MODE,
        entity_category=EntityCategory.CONFIG,
    ),
    VitotrolSwitchEntityDescription(
        key="energy_saving_mode",
        translation_key="energy_saving_mode",
        attr_id=ATTR_ENERGY_SAVING_MODE,
        entity_category=EntityCategory.CONFIG,
    ),
)


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
        for desc in SWITCH_DESCRIPTIONS:
            if desc.attr_id in catalog:
                entities.append(
                    VitotrolSwitch(coordinator, device, desc)
                )

    async_add_entities(entities)


class VitotrolSwitch(VitotrolEntity, SwitchEntity):
    """Switch entity for a Vitotrol on/off attribute."""

    entity_description: VitotrolSwitchEntityDescription

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        description: VitotrolSwitchEntityDescription,
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
        """Return True if the switch is on."""
        raw = self._get_attr_value(self._attr_id)
        if raw is None:
            return None
        return raw == "1"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.async_write(
            self._device, self._attr_id, "1"
        )
        self._update_coordinator_data(self._attr_id, "1")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.async_write(
            self._device, self._attr_id, "0"
        )
        self._update_coordinator_data(self._attr_id, "0")
        self.async_write_ha_state()
