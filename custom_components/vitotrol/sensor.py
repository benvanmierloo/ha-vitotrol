"""Sensor platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import AttributeTypeInfo, VitotrolDevice
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
    KNOWN_ATTR_IDS,
    OPERATING_MODE_CURRENT_MAP,
    WAY3_VALVE_STATUS_MAP,
)
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity

# Unit string -> (SensorDeviceClass, HA unit constant, SensorStateClass)
_UNIT_MAP: dict[str, tuple[SensorDeviceClass, str, SensorStateClass | None]] = {
    "°C": (SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, SensorStateClass.MEASUREMENT),
    "h": (SensorDeviceClass.DURATION, UnitOfTime.HOURS, SensorStateClass.TOTAL_INCREASING),
}


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
        catalog = coordinator.get_attribute_catalog(device.device_id)

        # Known sensors (enabled by default)
        for desc in SENSOR_DESCRIPTIONS:
            if desc.attr_id in catalog:
                entities.append(
                    VitotrolSensor(coordinator, device, desc)
                )

        # Dynamic sensors for discovered read-only attributes
        for attr_id, info in catalog.items():
            if attr_id in KNOWN_ATTR_IDS:
                continue
            if not info.readable:
                continue
            if info.writable:
                # Writable attrs are handled by number/select platforms
                continue

            entities.append(
                _create_dynamic_sensor(coordinator, device, info)
            )

    async_add_entities(entities)


def _create_dynamic_sensor(
    coordinator: VitotrolCoordinator,
    device: VitotrolDevice,
    info: AttributeTypeInfo,
) -> VitotrolDynamicSensor:
    """Create a dynamic sensor entity from GetTypeInfo metadata."""
    if info.enum_values is not None:
        # Enum sensor
        enum_map = {str(k): v for k, v in info.enum_values.items()}
        return VitotrolDynamicSensor(
            coordinator,
            device,
            info,
            device_class=SensorDeviceClass.ENUM,
            options=list(enum_map.values()),
            enum_values=enum_map,
            unit=None,
            state_class=None,
        )

    # Numeric or string sensor
    device_class = None
    unit = info.unit or None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT

    if info.unit in _UNIT_MAP:
        device_class, unit, state_class = _UNIT_MAP[info.unit]
    elif not info.unit:
        state_class = None

    return VitotrolDynamicSensor(
        coordinator,
        device,
        info,
        device_class=device_class,
        options=None,
        enum_values=None,
        unit=unit,
        state_class=state_class,
    )


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


class VitotrolDynamicSensor(VitotrolEntity, SensorEntity):
    """Sensor entity for a dynamically discovered attribute."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        info: AttributeTypeInfo,
        *,
        device_class: SensorDeviceClass | None,
        options: list[str] | None,
        enum_values: dict[str, str] | None,
        unit: str | None,
        state_class: SensorStateClass | None,
    ) -> None:
        super().__init__(coordinator, device, f"attr_{info.attr_id}")
        self._attr_id = info.attr_id
        self._attr_name = info.name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_options = options
        self._enum_values = enum_values

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

        if self._enum_values is not None:
            return self._enum_values.get(raw, raw)

        if self._attr_state_class is not None:
            try:
                return float(raw)
            except ValueError:
                return None

        return raw
