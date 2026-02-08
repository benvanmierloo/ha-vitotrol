"""Sensor platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import VitotrolDevice
from .const import (
    ATTR_BOILER_TEMP,
    ATTR_BURNER_HOURS_RUN,
    ATTR_BURNER_STARTS,
    ATTR_CURRENT_ERROR,
    ATTR_HEAT_WATER_OUT_TEMP,
    ATTR_HOT_WATER_OUT_TEMP,
    ATTR_HOT_WATER_TEMP,
    ATTR_INDOOR_TEMP,
    ATTR_OPERATING_MODE_CURRENT,
    ATTR_OUTDOOR_TEMP,
    ATTR_SMOKE_TEMP,
    ATTR_WAY3_VALVE_STATUS,
    CONF_CUSTOM_ATTRIBUTES,
    OPERATING_MODE_CURRENT_MAP,
    WAY3_VALVE_STATUS_MAP,
)
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity


@dataclass(frozen=True, kw_only=True)
class VitotrolSensorEntityDescription(SensorEntityDescription):
    """Describes a Vitotrol sensor entity."""

    attr_id: int
    enum_values: dict[str, str] | None = None


SENSOR_DESCRIPTIONS: tuple[VitotrolSensorEntityDescription, ...] = (
    VitotrolSensorEntityDescription(
        key="indoor_temperature",
        translation_key="indoor_temperature",
        attr_id=ATTR_INDOOR_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    VitotrolSensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        attr_id=ATTR_OUTDOOR_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    VitotrolSensorEntityDescription(
        key="boiler_temperature",
        translation_key="boiler_temperature",
        attr_id=ATTR_BOILER_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    VitotrolSensorEntityDescription(
        key="hot_water_temperature",
        translation_key="hot_water_temperature",
        attr_id=ATTR_HOT_WATER_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    VitotrolSensorEntityDescription(
        key="hot_water_outlet_temperature",
        translation_key="hot_water_outlet_temperature",
        attr_id=ATTR_HOT_WATER_OUT_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    VitotrolSensorEntityDescription(
        key="heating_water_outlet_temperature",
        translation_key="heating_water_outlet_temperature",
        attr_id=ATTR_HEAT_WATER_OUT_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    VitotrolSensorEntityDescription(
        key="smoke_temperature",
        translation_key="smoke_temperature",
        attr_id=ATTR_SMOKE_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    VitotrolSensorEntityDescription(
        key="burner_hours",
        translation_key="burner_hours",
        attr_id=ATTR_BURNER_HOURS_RUN,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    VitotrolSensorEntityDescription(
        key="burner_starts",
        translation_key="burner_starts",
        attr_id=ATTR_BURNER_STARTS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    VitotrolSensorEntityDescription(
        key="operating_mode",
        translation_key="operating_mode",
        attr_id=ATTR_OPERATING_MODE_CURRENT,
        device_class=SensorDeviceClass.ENUM,
        options=list(OPERATING_MODE_CURRENT_MAP.values()),
        enum_values=OPERATING_MODE_CURRENT_MAP,
    ),
    VitotrolSensorEntityDescription(
        key="valve_3way_status",
        translation_key="valve_3way_status",
        attr_id=ATTR_WAY3_VALVE_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=list(WAY3_VALVE_STATUS_MAP.values()),
        enum_values=WAY3_VALVE_STATUS_MAP,
    ),
    VitotrolSensorEntityDescription(
        key="current_error",
        translation_key="current_error",
        attr_id=ATTR_CURRENT_ERROR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


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
        device_data = coordinator.data.get(device.device_id, {})

        for desc in SENSOR_DESCRIPTIONS:
            if desc.attr_id in device_data:
                entities.append(
                    VitotrolSensor(coordinator, device, desc)
                )

        # Custom attribute sensors
        for custom in entry.options.get(CONF_CUSTOM_ATTRIBUTES, []):
            attr_id = custom["attr_id"]
            if attr_id in device_data:
                entities.append(
                    VitotrolCustomSensor(coordinator, device, custom)
                )

    async_add_entities(entities)


class VitotrolSensor(VitotrolEntity, SensorEntity):
    """Sensor entity for a known Vitotrol attribute."""

    entity_description: VitotrolSensorEntityDescription

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        description: VitotrolSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, device, description.key)
        self.entity_description = description
        self._attr_id = description.attr_id

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._attr_id in self._device_data

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        raw = self._get_attr_value(self._attr_id)
        if raw is None:
            return None

        if self.entity_description.enum_values is not None:
            return self.entity_description.enum_values.get(raw, raw)

        if self.entity_description.device_class in (
            SensorDeviceClass.TEMPERATURE,
            SensorDeviceClass.DURATION,
        ) or self.entity_description.state_class == SensorStateClass.TOTAL_INCREASING:
            try:
                return float(raw)
            except ValueError:
                return None

        return raw


class VitotrolCustomSensor(VitotrolEntity, SensorEntity):
    """Sensor entity for a user-defined custom attribute."""

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        custom: dict[str, Any],
    ) -> None:
        attr_id = custom["attr_id"]
        key = f"custom_{attr_id:04x}"
        super().__init__(coordinator, device, key)
        self._attr_id = attr_id
        self._attr_name = custom["name"].replace("_", " ").title()

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._attr_id in self._device_data

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value, attempting float conversion."""
        raw = self._get_attr_value(self._attr_id)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return raw
