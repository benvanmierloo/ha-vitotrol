"""Climate platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import VitotrolDevice
from .const import (
    ATTR_BURNER_STATE,
    ATTR_ENERGY_SAVING_MODE,
    ATTR_HEAT_NORMAL_TEMP,
    ATTR_INDOOR_TEMP,
    ATTR_OPERATING_MODE_CURRENT,
    ATTR_OPERATING_MODE_REQUESTED,
    ATTR_PARTY_MODE,
)
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity

# Mapping: HA HVAC mode -> Vitotrol OperatingModeRequested value
_HVAC_TO_VITOTROL: dict[HVACMode, str] = {
    HVACMode.OFF: "0",
    HVACMode.AUTO: "2",
    HVACMode.HEAT: "4",
}

_VITOTROL_TO_HVAC: dict[str, HVACMode] = {
    "0": HVACMode.OFF,
    "1": HVACMode.AUTO,  # DHW only -> treat as auto
    "2": HVACMode.AUTO,
    "3": HVACMode.HEAT,  # continuous reduced -> heat
    "4": HVACMode.HEAT,
}

PRESET_NONE = "none"
PRESET_ECO = "eco"
PRESET_BOOST = "boost"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitotrolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vitotrol climate entities."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[ClimateEntity] = []

    for device in coordinator.devices:
        device_data = coordinator.data.get(device.device_id, {})
        if ATTR_OPERATING_MODE_REQUESTED in device_data:
            entities.append(VitotrolClimate(coordinator, device))

    async_add_entities(entities)


class VitotrolClimate(VitotrolEntity, ClimateEntity):
    """Climate entity for a Vitotrol heating device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 3.0
    _attr_max_temp = 30.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT]
    _attr_preset_modes = [PRESET_NONE, PRESET_ECO, PRESET_BOOST]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_translation_key = "heating"
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
    ) -> None:
        super().__init__(coordinator, device, "climate")

    @property
    def current_temperature(self) -> float | None:
        """Return the current indoor temperature."""
        raw = self._get_attr_value(ATTR_INDOOR_TEMP)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature (normal heating setpoint)."""
        raw = self._get_attr_value(ATTR_HEAT_NORMAL_TEMP)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        raw = self._get_attr_value(ATTR_OPERATING_MODE_REQUESTED)
        if raw is None:
            return None
        return _VITOTROL_TO_HVAC.get(raw, HVACMode.AUTO)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        mode_raw = self._get_attr_value(ATTR_OPERATING_MODE_CURRENT)
        burner_raw = self._get_attr_value(ATTR_BURNER_STATE)

        if mode_raw == "0":
            return HVACAction.OFF

        if burner_raw == "1":
            return HVACAction.HEATING

        if burner_raw is not None:
            return HVACAction.IDLE

        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        eco = self._get_attr_value(ATTR_ENERGY_SAVING_MODE)
        party = self._get_attr_value(ATTR_PARTY_MODE)

        if party == "1":
            return PRESET_BOOST
        if eco == "1":
            return PRESET_ECO

        return PRESET_NONE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return

        temp = max(self._attr_min_temp, min(self._attr_max_temp, float(temp)))

        await self.coordinator.async_write(
            self._device, ATTR_HEAT_NORMAL_TEMP, str(temp)
        )

        # Optimistic update — mutate coordinator data so property reads see it
        self._update_coordinator_data(ATTR_HEAT_NORMAL_TEMP, str(temp))
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        value = _HVAC_TO_VITOTROL.get(hvac_mode)
        if value is None:
            return

        await self.coordinator.async_write(
            self._device, ATTR_OPERATING_MODE_REQUESTED, value
        )

        # Optimistic update
        self._update_coordinator_data(ATTR_OPERATING_MODE_REQUESTED, value)
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode (mutually exclusive: disable the other first)."""
        if preset_mode == PRESET_ECO:
            # Disable party mode first if active
            if self._get_attr_value(ATTR_PARTY_MODE) == "1":
                await self.coordinator.async_write(
                    self._device, ATTR_PARTY_MODE, "0"
                )
            await self.coordinator.async_write(
                self._device, ATTR_ENERGY_SAVING_MODE, "1"
            )
            self._update_coordinator_data(ATTR_PARTY_MODE, "0")
            self._update_coordinator_data(ATTR_ENERGY_SAVING_MODE, "1")
        elif preset_mode == PRESET_BOOST:
            # Disable eco mode first if active
            if self._get_attr_value(ATTR_ENERGY_SAVING_MODE) == "1":
                await self.coordinator.async_write(
                    self._device, ATTR_ENERGY_SAVING_MODE, "0"
                )
            await self.coordinator.async_write(
                self._device, ATTR_PARTY_MODE, "1"
            )
            self._update_coordinator_data(ATTR_ENERGY_SAVING_MODE, "0")
            self._update_coordinator_data(ATTR_PARTY_MODE, "1")
        elif preset_mode == PRESET_NONE:
            # Disable both
            if self._get_attr_value(ATTR_ENERGY_SAVING_MODE) == "1":
                await self.coordinator.async_write(
                    self._device, ATTR_ENERGY_SAVING_MODE, "0"
                )
            if self._get_attr_value(ATTR_PARTY_MODE) == "1":
                await self.coordinator.async_write(
                    self._device, ATTR_PARTY_MODE, "0"
                )
            self._update_coordinator_data(ATTR_ENERGY_SAVING_MODE, "0")
            self._update_coordinator_data(ATTR_PARTY_MODE, "0")

        self.async_write_ha_state()
