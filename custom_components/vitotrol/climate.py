"""Climate platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import VitotrolDevice
from .attributes import CLIMATE_CONFIGS, ClimateMeta
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

PRESET_NONE = "none"
PRESET_ECO = "eco"
PRESET_PARTY = "boost"


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
        catalog = coordinator.get_attribute_catalog(device.device_id)
        for config in CLIMATE_CONFIGS:
            if config.operating_mode_attr in catalog:
                entities.append(
                    VitotrolClimate(coordinator, device, catalog, config)
                )

    async_add_entities(entities)


class VitotrolClimate(VitotrolEntity, ClimateEntity):
    """Climate entity for a Vitotrol heating device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = 0.1
    _attr_target_temperature_step = 1
    _attr_min_temp = 3
    _attr_max_temp = 37
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        catalog: dict,
        climate_config: ClimateMeta,
    ) -> None:
        super().__init__(coordinator, device, climate_config.entity_key)
        self._attr_name = climate_config.circuit_name
        self._cfg = climate_config
        self._attr_hvac_modes = list(self._cfg.hvac_to_vitotrol.keys())

        # Min/max from GetTypeInfo for the target temp attribute
        target_info = catalog.get(self._cfg.target_temp_attr)
        if target_info:
            try:
                self._attr_min_temp = float(target_info.min_value)
            except (ValueError, TypeError):
                pass
            try:
                self._attr_max_temp = float(target_info.max_value)
            except (ValueError, TypeError):
                pass

        # Build preset list based on available attributes
        presets = [PRESET_NONE]
        if self._cfg.eco_mode_attr is not None and self._cfg.eco_mode_attr in catalog:
            presets.append(PRESET_ECO)
        if self._cfg.party_mode_attr is not None and self._cfg.party_mode_attr in catalog:
            presets.append(PRESET_PARTY)
        self._attr_preset_modes = presets

    def _polling_attr_ids(self) -> set[int]:
        """Climate reads multiple attributes."""
        ids = {
            self._cfg.target_temp_attr,
            self._cfg.operating_mode_attr,
        }
        for opt in (
            self._cfg.current_temp_attr,
            self._cfg.current_mode_attr,
            self._cfg.burner_state_attr,
            self._cfg.eco_mode_attr,
            self._cfg.party_mode_attr,
        ):
            if opt is not None:
                ids.add(opt)
        return ids

    @property
    def current_temperature(self) -> float | None:
        """Return the current indoor temperature."""
        if self._cfg.current_temp_attr is None:
            return None
        raw = self._get_attr_value(self._cfg.current_temp_attr)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            _LOGGER.debug(
                "Climate %s: cannot parse current_temp (attr %d) %r as float",
                self._device.device_name,
                self._cfg.current_temp_attr,
                raw,
            )
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        raw = self._get_attr_value(self._cfg.target_temp_attr)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            _LOGGER.debug(
                "Climate %s: cannot parse target_temp (attr %d) %r as float",
                self._device.device_name,
                self._cfg.target_temp_attr,
                raw,
            )
            return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        raw = self._get_attr_value(self._cfg.operating_mode_attr)
        if raw is None:
            return None
        return self._cfg.vitotrol_to_hvac.get(raw, HVACMode.AUTO)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        return self._cfg.resolve_action(
            self._get_attr_value(self._cfg.operating_mode_attr),
            self._get_attr_value(self._cfg.current_mode_attr)
            if self._cfg.current_mode_attr is not None
            else None,
            self._get_attr_value(self._cfg.burner_state_attr)
            if self._cfg.burner_state_attr is not None
            else None,
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self._cfg.party_mode_attr is not None:
            if self._get_attr_value(self._cfg.party_mode_attr) == "1":
                return PRESET_PARTY
        if self._cfg.eco_mode_attr is not None:
            if self._get_attr_value(self._cfg.eco_mode_attr) == "1":
                return PRESET_ECO
        return PRESET_NONE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return

        temp = max(self._attr_min_temp, min(self._attr_max_temp, float(temp)))
        str_temp = str(temp)
        old_value = self._get_attr_value(self._cfg.target_temp_attr)
        try:
            await self.coordinator.async_write(
                self._device, self._cfg.target_temp_attr, str_temp
            )
        except Exception as err:
            if old_value is not None:
                self._update_coordinator_data(self._cfg.target_temp_attr, old_value)
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Failed to set temperature for {self._device.device_name}: {err}"
            ) from err
        self._update_coordinator_data(self._cfg.target_temp_attr, str_temp)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        value = self._cfg.hvac_to_vitotrol.get(hvac_mode)
        if value is None:
            return

        old_value = self._get_attr_value(self._cfg.operating_mode_attr)
        try:
            await self.coordinator.async_write(
                self._device, self._cfg.operating_mode_attr, value
            )
        except Exception as err:
            if old_value is not None:
                self._update_coordinator_data(self._cfg.operating_mode_attr, old_value)
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Failed to set HVAC mode for {self._device.device_name}: {err}"
            ) from err
        self._update_coordinator_data(self._cfg.operating_mode_attr, value)
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode (mutually exclusive: disable the other first)."""
        eco_attr = self._cfg.eco_mode_attr
        party_attr = self._cfg.party_mode_attr

        # Check writable flags — skip read-only attrs with a warning (no error raised)
        catalog = self.coordinator.get_attribute_catalog(self._device.device_id)
        if eco_attr is not None:
            eco_info = catalog.get(eco_attr)
            if eco_info is not None and not eco_info.writable:
                _LOGGER.warning(
                    "Climate %s: eco_mode attr %d is read-only — skipping write",
                    self._device.device_name,
                    eco_attr,
                )
                eco_attr = None
        if party_attr is not None:
            party_info = catalog.get(party_attr)
            if party_info is not None and not party_info.writable:
                _LOGGER.warning(
                    "Climate %s: party_mode attr %d is read-only — skipping write",
                    self._device.device_name,
                    party_attr,
                )
                party_attr = None

        # Capture pre-write state for rollback
        old_eco = self._get_attr_value(eco_attr) if eco_attr is not None else None
        old_party = self._get_attr_value(party_attr) if party_attr is not None else None

        try:
            if preset_mode == PRESET_ECO and eco_attr is not None:
                if party_attr is not None and self._get_attr_value(party_attr) == "1":
                    await self.coordinator.async_write(self._device, party_attr, "0")
                await self.coordinator.async_write(self._device, eco_attr, "1")
                if party_attr is not None:
                    self._update_coordinator_data(party_attr, "0")
                self._update_coordinator_data(eco_attr, "1")

            elif preset_mode == PRESET_PARTY and party_attr is not None:
                if eco_attr is not None and self._get_attr_value(eco_attr) == "1":
                    await self.coordinator.async_write(self._device, eco_attr, "0")
                await self.coordinator.async_write(self._device, party_attr, "1")
                if eco_attr is not None:
                    self._update_coordinator_data(eco_attr, "0")
                self._update_coordinator_data(party_attr, "1")

            elif preset_mode == PRESET_NONE:
                if eco_attr is not None and self._get_attr_value(eco_attr) == "1":
                    await self.coordinator.async_write(self._device, eco_attr, "0")
                    self._update_coordinator_data(eco_attr, "0")
                if party_attr is not None and self._get_attr_value(party_attr) == "1":
                    await self.coordinator.async_write(self._device, party_attr, "0")
                    self._update_coordinator_data(party_attr, "0")

        except Exception as err:
            # Restore coordinator state; note that writes already sent to the
            # device cannot be rolled back, so device state may be inconsistent
            # until the next poll cycle.
            _LOGGER.warning(
                "Climate %s: preset write failed mid-sequence — device state "
                "may be inconsistent until next refresh",
                self._device.device_name,
            )
            if eco_attr is not None and old_eco is not None:
                self._update_coordinator_data(eco_attr, old_eco)
            if party_attr is not None and old_party is not None:
                self._update_coordinator_data(party_attr, old_party)
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Failed to set preset mode for {self._device.device_name}: {err}"
            ) from err

        self.async_write_ha_state()
