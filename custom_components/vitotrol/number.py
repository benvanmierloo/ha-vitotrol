"""Number platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import VitotrolDevice
from .const import (
    ATTR_HEAT_REDUCED_TEMP,
    ATTR_HOT_WATER_SETPOINT_TEMP,
    ATTR_PARTY_MODE_TEMP,
)
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity


@dataclass(frozen=True, kw_only=True)
class VitotrolNumberEntityDescription(NumberEntityDescription):
    """Describes a Vitotrol number entity."""

    attr_id: int


NUMBER_DESCRIPTIONS: tuple[VitotrolNumberEntityDescription, ...] = (
    VitotrolNumberEntityDescription(
        key="hot_water_setpoint",
        translation_key="hot_water_setpoint",
        attr_id=ATTR_HOT_WATER_SETPOINT_TEMP,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=10.0,
        native_max_value=60.0,
        native_step=1.0,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    VitotrolNumberEntityDescription(
        key="reduced_temperature_setpoint",
        translation_key="reduced_temperature_setpoint",
        attr_id=ATTR_HEAT_REDUCED_TEMP,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=3.0,
        native_max_value=30.0,
        native_step=0.5,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    VitotrolNumberEntityDescription(
        key="party_mode_temperature",
        translation_key="party_mode_temperature",
        attr_id=ATTR_PARTY_MODE_TEMP,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=10.0,
        native_max_value=30.0,
        native_step=0.5,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
)


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
        device_data = coordinator.data.get(device.device_id, {})
        for desc in NUMBER_DESCRIPTIONS:
            if desc.attr_id in device_data:
                entities.append(
                    VitotrolNumber(coordinator, device, desc)
                )

    async_add_entities(entities)


class VitotrolNumber(VitotrolEntity, NumberEntity):
    """Number entity for a writable Vitotrol temperature setpoint."""

    entity_description: VitotrolNumberEntityDescription

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        description: VitotrolNumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, device, description.key)
        self.entity_description = description
        self._attr_id = description.attr_id

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._attr_id in self._device_data

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        raw = self._get_attr_value(self._attr_id)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.coordinator.async_write(
            self._device, self._attr_id, str(value)
        )

        # Optimistic update — mutate coordinator data so property reads see it
        self._update_coordinator_data(self._attr_id, str(value))
        self.async_write_ha_state()
