"""Static attribute registry for the Viessmann Vitotrol integration.

Single source of truth for attribute metadata: English names, platform
routing, units, device classes, and enum translations.  Unknown attributes
discovered via GetTypeInfo fall back to dynamic behaviour in each platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.climate import HVACMode
from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)


@dataclass(frozen=True)
class AttrMeta:
    """Metadata for a known Vitotrol attribute."""

    name: str
    platform: str | None = None  # "sensor"|"binary_sensor"|"number"|"switch"|"select"|None
    enabled_by_default: bool = False
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    suggested_precision: int | None = None
    entity_category: EntityCategory | None = None
    on_values: tuple[str, ...] | None = None  # binary_sensor only
    enum_map: dict[str, str] | None = None  # raw_value -> english label


@dataclass(frozen=True)
class ClimateMeta:
    """Configuration for the climate composite entity."""

    current_temp_attr: int
    target_temp_attr: int
    operating_mode_attr: int
    current_mode_attr: int | None = None
    burner_state_attr: int | None = None
    eco_mode_attr: int | None = None
    party_mode_attr: int | None = None
    hvac_to_vitotrol: dict[HVACMode, str] = field(default_factory=dict)
    vitotrol_to_hvac: dict[str, HVACMode] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Attribute registry
# ---------------------------------------------------------------------------

ATTRIBUTE_REGISTRY: dict[int, AttrMeta] = {}

# -- Helper to register a batch with shared defaults ----------------------

def _temp_sensor(attr_id: int, name: str, *, enabled: bool = True) -> None:
    ATTRIBUTE_REGISTRY[attr_id] = AttrMeta(
        name=name,
        platform="sensor",
        enabled_by_default=enabled,
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_precision=1,
    )

# --- Sensors: temperatures ------------------------------------------------

_temp_sensor(5367, "Indoor temperature")
_temp_sensor(5373, "Outdoor temperature")
_temp_sensor(5374, "Boiler temperature")
_temp_sensor(5381, "Hot water temperature")
_temp_sensor(5372, "Exhaust gas temperature")
_temp_sensor(5382, "Hot water outlet temperature")
_temp_sensor(6052, "Heating water outlet temperature")
_temp_sensor(9786, "Hot water tank top temperature", enabled=False)
_temp_sensor(9787, "Hot water tank bottom temperature", enabled=False)

# --- Sensors: power -------------------------------------------------------

for _id, _name in (
    (9783, "Fuel cell electrical power"),
    (9836, "Fuel cell thermal power"),
    (9838, "Peak load burner thermal power"),
    (9839, "Electrical self-consumption"),
    (9840, "Grid electricity draw"),
):
    ATTRIBUTE_REGISTRY[_id] = AttrMeta(
        name=_name,
        platform="sensor",
        enabled_by_default=True,
        unit=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    )

# --- Sensors: energy ------------------------------------------------------

for _id, _name in (
    (11880, "Total electrical energy produced"),
    (9785, "Total fuel cell heat produced"),
):
    ATTRIBUTE_REGISTRY[_id] = AttrMeta(
        name=_name,
        platform="sensor",
        enabled_by_default=True,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )

# --- Sensors: percentages ------------------------------------------------

ATTRIBUTE_REGISTRY[4165] = AttrMeta(
    name="Burner modulation",
    platform="sensor",
    unit=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
)

ATTRIBUTE_REGISTRY[11252] = AttrMeta(
    name="Self-consumption ratio",
    platform="sensor",
    enabled_by_default=True,
    unit=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
)

ATTRIBUTE_REGISTRY[11959] = AttrMeta(
    name="Grid draw ratio",
    platform="sensor",
    enabled_by_default=True,
    unit=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
)

# --- Sensors: duration ----------------------------------------------------

for _id, _name in (
    (104, "Burner operating hours"),
    (9784, "Fuel cell operating hours"),
):
    ATTRIBUTE_REGISTRY[_id] = AttrMeta(
        name=_name,
        platform="sensor",
        enabled_by_default=True,
        unit=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )

# --- Sensors: counters ----------------------------------------------------

ATTRIBUTE_REGISTRY[111] = AttrMeta(
    name="Burner starts",
    platform="sensor",
    enabled_by_default=True,
    state_class=SensorStateClass.TOTAL_INCREASING,
)

# --- Sensors: gas ---------------------------------------------------------

for _id, _name, _enabled in (
    (9844, "Gas consumption this year", True),
    (9843, "Gas consumption last year", False),
):
    ATTRIBUTE_REGISTRY[_id] = AttrMeta(
        name=_name,
        platform="sensor",
        enabled_by_default=_enabled,
        unit=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )

# --- Sensors: CO2 ---------------------------------------------------------

for _id, _name, _enabled in (
    (9846, "CO2 savings this year", True),
    (9845, "CO2 savings last year", False),
):
    ATTRIBUTE_REGISTRY[_id] = AttrMeta(
        name=_name,
        platform="sensor",
        enabled_by_default=_enabled,
        unit=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )

# --- Sensors: enum status -------------------------------------------------

ATTRIBUTE_REGISTRY[708] = AttrMeta(
    name="Current operating mode",
    platform="sensor",
    enabled_by_default=True,
    device_class=SensorDeviceClass.ENUM,
    enum_map={"0": "Standby", "1": "Reduced", "2": "Normal", "3": "Continuous normal"},
)

ATTRIBUTE_REGISTRY[76] = AttrMeta(
    name="Party mode status",
    platform="sensor",
    device_class=SensorDeviceClass.ENUM,
    enum_map={"0": "Off", "1": "On"},
)

ATTRIBUTE_REGISTRY[88] = AttrMeta(
    name="Energy saving status",
    platform="sensor",
    device_class=SensorDeviceClass.ENUM,
    enum_map={"0": "Off", "1": "On"},
)

ATTRIBUTE_REGISTRY[270] = AttrMeta(
    name="External mode switch",
    platform="sensor",
    device_class=SensorDeviceClass.ENUM,
    enum_map={"0": "Off", "1": "On"},
)

ATTRIBUTE_REGISTRY[7987] = AttrMeta(
    name="Heating circuit 1 type",
    platform="sensor",
    device_class=SensorDeviceClass.ENUM,
    enum_map={"0": "Not present", "1": "Direct circuit", "2": "Mixer circuit"},
)

ATTRIBUTE_REGISTRY[10761] = AttrMeta(
    name="Hot water sensor status",
    platform="sensor",
    device_class=SensorDeviceClass.ENUM,
    enum_map={
        "0": "OK",
        "1": "Short circuit",
        "2": "Open circuit",
        "3": "Unknown",
        "4": "Unknown",
        "5": "Unknown",
        "6": "Not present",
    },
)

ATTRIBUTE_REGISTRY[12526] = AttrMeta(
    name="Fuel cell maintenance status",
    platform="sensor",
    device_class=SensorDeviceClass.ENUM,
    enum_map={
        "0": "No maintenance required",
        "1": "Regular maintenance",
        "2": "Overhaul stop",
        "3": "End of lifetime",
    },
)

# --- Sensors: other -------------------------------------------------------

ATTRIBUTE_REGISTRY[7184] = AttrMeta(
    name="Current error",
    platform="sensor",
    enabled_by_default=True,
)

ATTRIBUTE_REGISTRY[897] = AttrMeta(
    name="Error byte",
    platform="sensor",
    entity_category=EntityCategory.DIAGNOSTIC,
)

# --- Binary sensors -------------------------------------------------------

ATTRIBUTE_REGISTRY[600] = AttrMeta(
    name="Burner",
    platform="binary_sensor",
    enabled_by_default=True,
    device_class=BinarySensorDeviceClass.RUNNING,
    on_values=("1",),
)

ATTRIBUTE_REGISTRY[245] = AttrMeta(
    name="Internal pump",
    platform="binary_sensor",
    enabled_by_default=True,
    device_class=BinarySensorDeviceClass.RUNNING,
    on_values=("1", "3"),
)

ATTRIBUTE_REGISTRY[729] = AttrMeta(
    name="Heating circuit pump",
    platform="binary_sensor",
    enabled_by_default=True,
    device_class=BinarySensorDeviceClass.RUNNING,
    on_values=("1",),
)

ATTRIBUTE_REGISTRY[7181] = AttrMeta(
    name="Circulation pump",
    platform="binary_sensor",
    enabled_by_default=True,
    device_class=BinarySensorDeviceClass.RUNNING,
    on_values=("1",),
)

ATTRIBUTE_REGISTRY[5280] = AttrMeta(
    name="Storage charge pump",
    platform="binary_sensor",
    enabled_by_default=True,
    device_class=BinarySensorDeviceClass.RUNNING,
    on_values=("1",),
)

ATTRIBUTE_REGISTRY[714] = AttrMeta(
    name="Holiday program",
    platform="binary_sensor",
    enabled_by_default=True,
    on_values=("1",),
)

ATTRIBUTE_REGISTRY[717] = AttrMeta(
    name="Frost protection",
    platform="binary_sensor",
    enabled_by_default=True,
    device_class=BinarySensorDeviceClass.SAFETY,
    on_values=("1",),
)

# --- Numbers --------------------------------------------------------------

ATTRIBUTE_REGISTRY[85] = AttrMeta(
    name="Reduced temperature setpoint",
    platform="number",
    enabled_by_default=True,
    unit=UnitOfTemperature.CELSIUS,
    device_class=NumberDeviceClass.TEMPERATURE,
    entity_category=EntityCategory.CONFIG,
)

ATTRIBUTE_REGISTRY[79] = AttrMeta(
    name="Party mode temperature",
    platform="number",
    enabled_by_default=True,
    unit=UnitOfTemperature.CELSIUS,
    device_class=NumberDeviceClass.TEMPERATURE,
    entity_category=EntityCategory.CONFIG,
)

ATTRIBUTE_REGISTRY[11881] = AttrMeta(
    name="Hot water setpoint",
    platform="number",
    enabled_by_default=True,
    unit=UnitOfTemperature.CELSIUS,
    device_class=NumberDeviceClass.TEMPERATURE,
    entity_category=EntityCategory.CONFIG,
)

ATTRIBUTE_REGISTRY[51] = AttrMeta(
    name="Hot water setpoint temperature",
    platform="number",
    enabled_by_default=True,
    unit=UnitOfTemperature.CELSIUS,
    device_class=NumberDeviceClass.TEMPERATURE,
    entity_category=EntityCategory.CONFIG,
)

ATTRIBUTE_REGISTRY[949] = AttrMeta(
    name="Hot water setpoint 2",
    platform="number",
    unit=UnitOfTemperature.CELSIUS,
    device_class=NumberDeviceClass.TEMPERATURE,
    entity_category=EntityCategory.CONFIG,
)

ATTRIBUTE_REGISTRY[2869] = AttrMeta(
    name="Heating curve slope",
    platform="number",
    entity_category=EntityCategory.CONFIG,
)

ATTRIBUTE_REGISTRY[2875] = AttrMeta(
    name="Heating curve level",
    platform="number",
    entity_category=EntityCategory.CONFIG,
)

# --- Switches -------------------------------------------------------------

ATTRIBUTE_REGISTRY[7855] = AttrMeta(
    name="Party mode",
    platform="switch",
    enabled_by_default=True,
)

ATTRIBUTE_REGISTRY[7852] = AttrMeta(
    name="Energy saving mode",
    platform="switch",
    enabled_by_default=True,
)

# --- Selects --------------------------------------------------------------

ATTRIBUTE_REGISTRY[9782] = AttrMeta(
    name="Fuel cell operating mode",
    platform="select",
    enabled_by_default=True,
    enum_map={
        "0": "Service mode",
        "1": "Energy manager on",
        "2": "Energy manager off",
        "3": "Shutdown",
        "4": "CSM",
        "5": "Party mode",
        "6": "Holiday on",
        "7": "Holiday off",
    },
)

ATTRIBUTE_REGISTRY[801] = AttrMeta(
    name="Heating system schema",
    platform="select",
    enum_map={
        "0": "No HC/storage",
        "1": "1 A1",
        "2": "2 A1 + WW",
        "3": "3 M2",
        "4": "4 M2 + WW",
        "5": "5 A1 + M2",
        "6": "6 A1 + M2 + WW",
        "7": "7 M2 + M3",
        "8": "8 M2 + M3 + WW",
        "9": "9 A1 + M2 + M3",
        "10": "10 A1 + M2 + M3 + WW",
    },
)

ATTRIBUTE_REGISTRY[865] = AttrMeta(
    name="Maintenance mode",
    platform="select",
    enum_map={"0": "Inactive", "1": "Active"},
)

ATTRIBUTE_REGISTRY[990] = AttrMeta(
    name="Error manager",
    platform="select",
    enum_map={"0": "None", "1": "Error manager"},
)

ATTRIBUTE_REGISTRY[7271] = AttrMeta(
    name="Solar controller",
    platform="select",
    enum_map={
        "0": "None",
        "1": "Vitosolic 100",
        "2": "Vitosolic 200",
        "3": "Solar module SM1",
        "4": "SM1 with DT2",
    },
)

# --- Platform=None (used by climate or not entity-worthy) -----------------

ATTRIBUTE_REGISTRY[92] = AttrMeta(name="Operating mode")
ATTRIBUTE_REGISTRY[82] = AttrMeta(name="Room temperature setpoint")
ATTRIBUTE_REGISTRY[5385] = AttrMeta(name="Device date/time")
ATTRIBUTE_REGISTRY[306] = AttrMeta(name="Holiday start date")
ATTRIBUTE_REGISTRY[309] = AttrMeta(name="Holiday end date")
ATTRIBUTE_REGISTRY[7191] = AttrMeta(name="Heating schedule")
ATTRIBUTE_REGISTRY[7192] = AttrMeta(name="Hot water schedule")
ATTRIBUTE_REGISTRY[7193] = AttrMeta(name="Circulation schedule")

# ---------------------------------------------------------------------------
# History sensors (generated programmatically)
# ---------------------------------------------------------------------------

# Electrical energy -- last year monthly (IDs 9847-9858)
for _i in range(12):
    ATTRIBUTE_REGISTRY[9847 + _i] = AttrMeta(
        name=f"Elec. energy last year month {_i + 1}",
        platform="sensor",
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
    )

# Electrical energy -- this year monthly (IDs 9859-9870)
for _i in range(12):
    ATTRIBUTE_REGISTRY[9859 + _i] = AttrMeta(
        name=f"Elec. energy this year month {_i + 1}",
        platform="sensor",
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
    )

# Electrical energy -- this month daily (IDs 9953, 9955-9984; skip 9954)
_elec_this_month_ids = [9953] + list(range(9955, 9985))
for _day, _id in enumerate(_elec_this_month_ids, start=1):
    ATTRIBUTE_REGISTRY[_id] = AttrMeta(
        name=f"Elec. energy this month day {_day}",
        platform="sensor",
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
    )

# Electrical energy -- last month daily (IDs 9985-10015)
for _i in range(31):
    ATTRIBUTE_REGISTRY[9985 + _i] = AttrMeta(
        name=f"Elec. energy last month day {_i + 1}",
        platform="sensor",
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
    )

# CO2 savings -- last year monthly (IDs 9873, 9875-9885; skip 9874)
_co2_last_year_ids = [9873] + list(range(9875, 9886))
for _month, _id in enumerate(_co2_last_year_ids, start=1):
    ATTRIBUTE_REGISTRY[_id] = AttrMeta(
        name=f"CO2 savings last year month {_month}",
        platform="sensor",
        unit=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    )

# CO2 savings -- this year monthly (IDs 9886-9897)
for _i in range(12):
    ATTRIBUTE_REGISTRY[9886 + _i] = AttrMeta(
        name=f"CO2 savings this year month {_i + 1}",
        platform="sensor",
        unit=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    )

# CO2 savings -- this month daily (IDs 10016-10046)
for _i in range(31):
    ATTRIBUTE_REGISTRY[10016 + _i] = AttrMeta(
        name=f"CO2 savings this month day {_i + 1}",
        platform="sensor",
        unit=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    )

# CO2 savings -- last month daily (IDs 10047-10077)
for _i in range(31):
    ATTRIBUTE_REGISTRY[10047 + _i] = AttrMeta(
        name=f"CO2 savings last month day {_i + 1}",
        platform="sensor",
        unit=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    )

# Clean up loop variables from module scope
del _i, _id, _name, _enabled, _day, _month
del _elec_this_month_ids, _co2_last_year_ids

# ---------------------------------------------------------------------------
# Climate configuration
# ---------------------------------------------------------------------------

CLIMATE_CONFIG = ClimateMeta(
    current_temp_attr=5367,
    target_temp_attr=82,
    operating_mode_attr=92,
    current_mode_attr=708,
    burner_state_attr=600,
    eco_mode_attr=7852,
    party_mode_attr=7855,
    hvac_to_vitotrol={
        HVACMode.OFF: "0",
        HVACMode.AUTO: "2",
        HVACMode.HEAT: "4",
    },
    vitotrol_to_hvac={
        "0": HVACMode.OFF,
        "1": HVACMode.AUTO,
        "2": HVACMode.AUTO,
        "3": HVACMode.HEAT,
        "4": HVACMode.HEAT,
    },
)
