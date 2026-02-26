"""Base entity for the Viessmann Vitotrol integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    PERCENTAGE,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AttributeTypeInfo, VitotrolDevice
from .const import DOMAIN
from .coordinator import VitotrolCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class InferredMeta:
    """Inferred metadata for an unknown Vitotrol attribute."""

    platform: str | None
    display_name: str
    device_class: str | None = None
    state_class: str | None = None
    unit: str | None = None
    suggested_precision: int | None = None


def _is_binary_enum(info: AttributeTypeInfo) -> bool:
    """Return True if enum values look like a simple on/off pair."""
    if info.enum_values is None:
        return False
    labels = {str(v).lower() for v in info.enum_values.values()}
    return labels <= {"aus", "ein"}


def _group_prefix(group: str) -> str:
    """Extract the subsystem suffix after '~' from a group string."""
    if "~" in group:
        return group.split("~")[-1]
    return ""


def _infer_numeric_meta(name: str) -> tuple[str | None, str | None, str | None, int | None]:
    """Return (device_class, unit, state_class, suggested_precision) for a numeric attr name."""
    n = name.lower()
    if n.startswith("temp_") or n.startswith("info_temp_"):
        return SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, SensorStateClass.MEASUREMENT, 1
    if n.startswith("anzahl_brennerstunden"):
        return SensorDeviceClass.DURATION, UnitOfTime.HOURS, SensorStateClass.TOTAL_INCREASING, None
    if n.startswith("anzahl_brennerstart"):
        return None, None, SensorStateClass.TOTAL_INCREASING, None
    if n.startswith("info_brenner_modulation"):
        return None, PERCENTAGE, SensorStateClass.MEASUREMENT, None
    if n.startswith("info_historie_eee_"):
        return SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, SensorStateClass.TOTAL, None
    if n.startswith("info_historie_co2_"):
        return SensorDeviceClass.WEIGHT, UnitOfMass.KILOGRAMS, SensorStateClass.TOTAL, None
    if "leistung" in n and n.startswith("info_"):
        return SensorDeviceClass.POWER, UnitOfPower.WATT, SensorStateClass.MEASUREMENT, None
    if "verbrauch" in n and n.startswith("info_"):
        return SensorDeviceClass.GAS, UnitOfVolume.CUBIC_METERS, SensorStateClass.TOTAL_INCREASING, None
    if "einsparung" in n and n.startswith("info_"):
        return SensorDeviceClass.WEIGHT, UnitOfMass.KILOGRAMS, SensorStateClass.TOTAL_INCREASING, None
    if n.startswith("info_energie_"):
        return SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, SensorStateClass.TOTAL_INCREASING, None
    if n.startswith("info_verhaeltnis_"):
        return None, PERCENTAGE, SensorStateClass.MEASUREMENT, None
    return None, None, SensorStateClass.MEASUREMENT, None


def infer_unknown_metadata(info: AttributeTypeInfo) -> InferredMeta:
    """Infer platform and HA metadata for an attribute not in the registry."""
    prefix = _group_prefix(info.group)
    display_name = f"{prefix}: {info.name}" if prefix else info.name

    t = info.type

    if t == "Date":
        return InferredMeta(platform="datetime", display_name=display_name)

    if t == "CircuitTime":
        return InferredMeta(platform=None, display_name=display_name)

    if t == "ENUM":
        if _is_binary_enum(info) and not info.writable:
            return InferredMeta(platform="binary_sensor", display_name=display_name)
        if info.writable:
            return InferredMeta(platform="select", display_name=display_name)
        return InferredMeta(platform="sensor", display_name=display_name)

    if t in ("Double", "Integer"):
        if info.writable and info.enum_values is None:
            return InferredMeta(platform="number", display_name=display_name)
        device_class, unit, state_class, precision = _infer_numeric_meta(info.name)
        return InferredMeta(
            platform="sensor",
            display_name=display_name,
            device_class=device_class,
            state_class=state_class,
            unit=unit,
            suggested_precision=precision,
        )

    # String and anything else
    return InferredMeta(platform="sensor", display_name=display_name)


class VitotrolEntity(CoordinatorEntity[VitotrolCoordinator]):
    """Base class for all Vitotrol entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._device_id = device.device_id
        self._attr_unique_id = f"{device.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.device_id))},
            name=device.device_name,
            manufacturer="Viessmann",
            model="Vitotrol",
            configuration_url=(
                "https://vitotrolapp.viessmann-climatesolutions.com"
            ),
        )

    # ------------------------------------------------------------------
    # Lifecycle — register/unregister attr_ids for polling
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Register attr_ids with the coordinator when entity is added."""
        await super().async_added_to_hass()
        attr_ids = self._polling_attr_ids()
        if attr_ids:
            self.coordinator.register_entity_attrs(
                self._device_id, self._attr_unique_id, attr_ids
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister attr_ids when entity is removed."""
        self.coordinator.unregister_entity_attrs(
            self._device_id, self._attr_unique_id
        )
        await super().async_will_remove_from_hass()

    def _polling_attr_ids(self) -> set[int]:
        """Return the set of attr_ids this entity needs polled.

        Default: uses self._vitotrol_attr_id if present. Override in
        entities that read multiple attributes (e.g. climate).
        """
        attr_id = getattr(self, "_vitotrol_attr_id", None)
        if attr_id is not None:
            return {attr_id}
        return set()

    # ------------------------------------------------------------------
    # Data access helpers
    # ------------------------------------------------------------------

    @property
    def _device_data(self) -> dict[int, str]:
        """Return the data dict for this entity's device."""
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.get(self._device_id, {})

    def _get_attr_value(self, attr_id: int) -> str | None:
        """Return a raw attribute value string, or None if unavailable."""
        return self._device_data.get(attr_id)

    def _update_coordinator_data(self, attr_id: int, value: str) -> None:
        """Optimistically update a value in the coordinator data store.

        Mutates coordinator.data directly so that property-based state
        reads pick up the new value immediately.
        """
        if self.coordinator.data is None:
            return
        device_data = self.coordinator.data.get(self._device_id)
        if device_data is None:
            return
        device_data[attr_id] = value
