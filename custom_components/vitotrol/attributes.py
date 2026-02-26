"""Static attribute registry for the Viessmann Vitotrol integration.

Single source of truth for attribute metadata: English names, platform
routing, units, device classes, and enum translations.  Unknown attributes
discovered via GetTypeInfo fall back to dynamic behaviour in each platform.

To add a new attribute:
  1. Add a row to _TABLE  (id, name, enabled, category)
  2. If it has enums, add an entry to _ENUM_MAPS
  3. If it's a binary_sensor with non-default on-values, add to _ON_VALUES
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.climate import HVACAction, HVACMode
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
    platform: str | None = None
    enabled_by_default: bool = False
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    suggested_precision: int | None = None
    entity_category: EntityCategory | None = None
    on_values: tuple[str, ...] | None = None
    enum_map: dict[str, str] | None = None


@dataclass(frozen=True)
class ClimateMeta:
    """Configuration for the climate composite entity."""

    current_temp_attr: int
    target_temp_attr: int
    operating_mode_attr: int
    resolve_action: Callable[
        [str | None, str | None, str | None], HVACAction | None
    ]
    current_mode_attr: int | None = None
    burner_state_attr: int | None = None
    eco_mode_attr: int | None = None
    party_mode_attr: int | None = None
    hvac_to_vitotrol: dict[HVACMode, str] = field(default_factory=dict)
    vitotrol_to_hvac: dict[str, HVACMode] = field(default_factory=dict)


# ============================================================================
# Category templates — shared HA metadata for groups of attributes
# ============================================================================
# Each key maps to the AttrMeta fields shared by every attribute in that
# category.  The builder loop below merges these with per-row data.

_CATEGORIES: dict[str, dict] = {
    # -- Sensor categories ---------------------------------------------------
    "temp":       dict(platform="sensor", unit=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT, suggested_precision=1),
    "power":      dict(platform="sensor", unit=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    "energy":     dict(platform="sensor", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING),
    "energy_h":   dict(platform="sensor", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.MEASUREMENT),
    "pct":        dict(platform="sensor", unit=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT),
    "duration":   dict(platform="sensor", unit=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.TOTAL_INCREASING),
    "counter":    dict(platform="sensor", state_class=SensorStateClass.TOTAL_INCREASING),
    "gas":        dict(platform="sensor", unit=UnitOfVolume.CUBIC_METERS, device_class=SensorDeviceClass.GAS, state_class=SensorStateClass.TOTAL_INCREASING),
    "weight":     dict(platform="sensor", unit=UnitOfMass.KILOGRAMS, device_class=SensorDeviceClass.WEIGHT, state_class=SensorStateClass.TOTAL_INCREASING),
    "weight_h":   dict(platform="sensor", unit=UnitOfMass.KILOGRAMS, device_class=SensorDeviceClass.WEIGHT, state_class=SensorStateClass.MEASUREMENT),
    "enum":       dict(platform="sensor", device_class=SensorDeviceClass.ENUM),
    "text":       dict(platform="sensor"),
    "cop":        dict(platform="sensor", state_class=SensorStateClass.MEASUREMENT, suggested_precision=1),
    "diag":       dict(platform="sensor", entity_category=EntityCategory.DIAGNOSTIC),
    # -- Binary sensor categories --------------------------------------------
    "running":    dict(platform="binary_sensor", device_class=BinarySensorDeviceClass.RUNNING, on_values=("1",)),
    "safety":     dict(platform="binary_sensor", device_class=BinarySensorDeviceClass.SAFETY, on_values=("1",)),
    "bool":       dict(platform="binary_sensor", on_values=("1",)),
    # -- Number categories ---------------------------------------------------
    "num_temp":   dict(platform="number", unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE, entity_category=EntityCategory.CONFIG),
    "num":        dict(platform="number", entity_category=EntityCategory.CONFIG),
    # -- Switch / select / none ----------------------------------------------
    "switch":     dict(platform="switch"),
    "select":     dict(platform="select"),
    "none":       dict(),
}


# ============================================================================
# Attribute table — THE master list.  One row per attribute.
# ============================================================================
#
#   (id,    name,                               enabled, category)
#
# • "category" determines platform + unit + device_class + state_class etc.
# • For enums, add entry to _ENUM_MAPS below.
# • For binary_sensor on_values != ("1",), add entry to _ON_VALUES below.

_TABLE: list[tuple[int, str, bool, str]] = [
    # fmt: off

    # ---- Temperature sensors ------------------------------------------------
    (5367,  "Indoor temperature",                True,   "temp"),
    (5373,  "Outdoor temperature",               True,   "temp"),
    (5374,  "Boiler temperature",                True,   "temp"),
    (5381,  "Hot water temperature",             True,   "temp"),
    (5372,  "Exhaust gas temperature",           True,   "temp"),
    (5382,  "Hot water outlet temperature",      True,   "temp"),
    (6052,  "Heating water outlet temperature",  True,   "temp"),
    (9786,  "Hot water tank top temperature",    False,  "temp"),
    (9787,  "Hot water tank bottom temperature", False,  "temp"),

    # ---- Power sensors ------------------------------------------------------
    (9783,  "Fuel cell electrical power",        False,   "power"),
    (9836,  "Fuel cell thermal power",           False,   "power"),
    (9838,  "Peak load burner thermal power",    False,   "power"),
    (9839,  "Electrical self-consumption",       False,   "power"),
    (9840,  "Grid electricity draw",             False,   "power"),

    # ---- Energy sensors (cumulative) ----------------------------------------
    (11880, "Total electrical energy produced",  False,   "energy"),
    (9785,  "Total fuel cell heat produced",     False,   "energy"),

    # ---- Percentage sensors -------------------------------------------------
    (4165,  "Burner modulation",                 False,  "pct"),
    (11252, "Self-consumption ratio",            False,  "pct"),
    (11959, "Grid draw ratio",                   False,  "pct"),

    # ---- Duration sensors ---------------------------------------------------
    (104,   "Burner operating hours",            True,   "duration"),
    (9784,  "Fuel cell operating hours",         False,  "duration"),

    # ---- Counter sensors ----------------------------------------------------
    (111,   "Burner starts",                     True,   "counter"),

    # ---- Gas sensors --------------------------------------------------------
    (9844,  "Gas consumption this year",         False,  "gas"),
    (9843,  "Gas consumption last year",         False,  "gas"),

    # ---- CO2 sensors (cumulative) -------------------------------------------
    (9846,  "CO2 savings this year",             False,  "weight"),
    (9845,  "CO2 savings last year",             False,  "weight"),

    # ---- Enum status sensors (see _ENUM_MAPS) ------------------------------
    (708,   "Current operating mode",            True,   "enum"),
    (76,    "Party mode status",                 False,  "enum"),
    (88,    "Energy saving status",              False,  "enum"),
    (270,   "External mode switch",              False,  "enum"),
    (7987,  "Heating circuit 1 type",            False,  "enum"),
    (10761, "Hot water sensor status",           False,  "enum"),
    (12526, "Fuel cell maintenance status",      False,  "enum"),

    # ---- Other sensors ------------------------------------------------------
    (7184,  "Current error",                     True,   "diag"),
    (897,   "Error byte",                        False,  "diag"),

    # ---- Binary sensors (see _ON_VALUES for non-default) --------------------
    (600,   "Burner",                            True,   "running"),
    (245,   "Internal pump",                     False,   "running"),  # see _ON_VALUES
    (729,   "Heating circuit pump",              False,   "running"),
    (7181,  "Circulation pump",                  False,   "running"),
    (5280,  "Storage charge pump",               False,   "running"),
    (714,   "Holiday program",                   False,   "bool"),
    (717,   "Frost protection",                  False,   "safety"),

    # ---- Number entities ----------------------------------------------------
    (85,    "Reduced temperature setpoint",      True,   "num_temp"),
    (79,    "Party mode temperature",            True,   "num_temp"),
    (11881, "Hot water setpoint",                True,   "num_temp"),
    (51,    "Hot water setpoint temperature",    True,   "num_temp"),
    (949,   "Hot water setpoint 2",              False,  "num_temp"),
    (2869,  "Heating curve slope",               False,  "num"),
    (2875,  "Heating curve level",               False,  "num"),

    # ---- Switch entities ----------------------------------------------------
    (7855,  "Party mode",                        True,   "switch"),
    (7852,  "Energy saving mode",                True,   "switch"),

    # ---- Select entities (see _ENUM_MAPS) -----------------------------------
    (9782,  "Fuel cell operating mode",          False,   "select"),
    (801,   "Heating system schema",             False,  "select"),
    (865,   "Maintenance mode",                  False,  "select"),
    (990,   "Error manager",                     False,  "select"),
    (7271,  "Solar controller",                  False,  "select"),

    # ---- No standalone entity (used by climate / not parseable) -------------
    (92,    "Operating mode",                    False,  "select"),  # also used by climate
    (82,    "Room temperature setpoint",         False,  "none"),  # climate RW
    (5385,  "Device date/time",                  False,  "none"),
    (306,   "Holiday start date",                False,  "none"),
    (309,   "Holiday end date",                  False,  "none"),
    (7191,  "Heating schedule",                  False,  "none"),
    (7192,  "Hot water schedule",                False,  "none"),
    (7193,  "Circulation schedule",              False,  "none"),

    # ====================================================================
    # Heat pump attributes (VT 200, Vitocal, etc.)
    # ====================================================================

    # ---- HP temperature sensors ---------------------------------------------
    (7299,  "Indoor temperature",               True,   "temp"),
    (7692,  "Outdoor temperature",              True,   "temp"),
    (7698,  "Flow temperature",                 True,   "temp"),
    (7714,  "Hot water temperature",            True,   "temp"),
    (7716,  "Hot water tank bottom temperature", False,  "temp"),
    (7694,  "Primary flow temperature",         False,  "temp"),
    (7696,  "Primary return temperature",       False,  "temp"),
    (7700,  "Secondary return temperature",     False,  "temp"),

    # ---- HP energy sensors (cumulative) -------------------------------------
    (7350,  "DHW energy",                       True,   "energy"),
    (8964,  "Heating energy",                   True,   "energy"),
    (8966,  "Electrical energy consumption",    True,   "energy"),

    # ---- HP COP sensors (seasonal performance factor) -----------------------
    (7334,  "COP heating",                      True,   "cop"),
    (7335,  "COP DHW",                          True,   "cop"),
    (7364,  "COP total",                        True,   "cop"),

    # ---- HP duration sensors ------------------------------------------------
    (6650,  "Compressor operating hours",       True,   "duration"),

    # ---- HP counter sensors -------------------------------------------------
    (6830,  "Compressor starts",                True,   "counter"),

    # ---- HP enum status sensors (see _ENUM_MAPS) ----------------------------
    (8537,  "Current operating mode",           True,   "enum"),
    (6181,  "Heating system schema",            False,  "enum"),
    (6524,  "External mixer status",            False,  "enum"),

    # ---- HP diagnostic sensors ----------------------------------------------
    (7209,  "Current error",                    True,   "diag"),
    (8051,  "Screed drying runtime 1",          False,  "diag"),
    (8052,  "Screed drying runtime 2",          False,  "diag"),
    (8053,  "Screed drying runtime 3",          False,  "diag"),

    # ---- HP binary sensors --------------------------------------------------
    (6710,  "Compressor",                       True,   "running"),
    (12665, "Compressor 2",                     False,  "running"),
    (6746,  "Heating circuit pump",             False,  "running"),
    (6762,  "Circulation pump",                 False,  "running"),
    (6768,  "Storage charge pump",              False,  "running"),
    (8129,  "Holiday program",                  False,  "bool"),

    # ---- HP number entities -------------------------------------------------
    (6373,  "Reduced temperature setpoint",     True,   "num_temp"),
    (8055,  "Party mode temperature",           True,   "num_temp"),
    (7142,  "Hot water setpoint temperature",   True,   "num_temp"),
    (7139,  "Hot water setpoint 2",             False,  "num_temp"),
    (6165,  "Frost protection temperature",     False,  "num_temp"),
    (6217,  "Bivalence temperature",            False,  "num_temp"),
    (6332,  "Buffer tank hysteresis",           False,  "num_temp"),
    (6333,  "Buffer tank max temperature",      False,  "num_temp"),
    (6359,  "Max flow temperature",             False,  "num_temp"),
    (6442,  "Flow temperature hysteresis",      False,  "num_temp"),
    (7133,  "DHW hysteresis",                   False,  "num_temp"),
    (7134,  "DHW additional heater hysteresis", False,  "num_temp"),
    (7140,  "Hot water max temperature",        False,  "num_temp"),
    (7782,  "Flow hysteresis off",              False,  "num_temp"),
    (6363,  "Heating curve slope",              False,  "num"),
    (6366,  "Heating curve level",              False,  "num"),
    (7051,  "Compressor power level",           False,  "num"),

    # ---- HP switch entities -------------------------------------------------
    (8059,  "Party mode",                       True,   "switch"),
    (8062,  "Energy saving mode",               True,   "switch"),
    (6331,  "Buffer tank enabled",              False,  "switch"),
    (8066,  "One-time DHW charge",              False,  "switch"),

    # ---- HP select entities (see _ENUM_MAPS) --------------------------------
    (6976,  "Solar controller",                 False,  "select"),
    (7373,  "Operating mode",                   False,  "select"),

    # ---- HP — no standalone entity (climate / not parseable) ----------------
    (6369,  "Room temperature setpoint",        False,  "none"),
    (7033,  "Device date/time",                 False,  "none"),
    (8142,  "Holiday start date",               False,  "none"),
    (8143,  "Holiday end date",                 False,  "none"),
    (7292,  "Heating schedule",                 False,  "none"),
    (7296,  "Hot water schedule",               False,  "none"),
    (7543,  "Circulation schedule",             False,  "none"),

    # fmt: on
]


# ============================================================================
# Enum maps — keyed by attr_id
# ============================================================================
# Used by "enum" category sensors and "select" entities.  The dict values
# are the English labels shown in HA.

_ENUM_MAPS: dict[int, dict[str, str]] = {
    # -- Enum status sensors --------------------------------------------------
    708:   {"0": "Standby", "1": "Reduced", "2": "Normal", "3": "Continuous normal"},
    76:    {"0": "Off", "1": "On"},
    88:    {"0": "Off", "1": "On"},
    270:   {"0": "Off", "1": "On"},
    7987:  {"0": "Not present", "1": "Direct circuit", "2": "Mixer circuit"},
    10761: {
        "0": "OK", "1": "Short circuit", "2": "Open circuit",
        "3": "Unknown", "4": "Unknown", "5": "Unknown", "6": "Not present",
    },
    12526: {
        "0": "No maintenance required", "1": "Regular maintenance",
        "2": "Overhaul stop", "3": "End of lifetime",
    },
    # -- Select entities ------------------------------------------------------
    92: {
        "0": "Off", "1": "DHW only", "2": "Heating + DHW",
        "3": "Continuous reduced", "4": "Continuous normal",
    },
    9782: {
        "0": "Service mode", "1": "Energy manager on", "2": "Energy manager off",
        "3": "Shutdown", "4": "CSM", "5": "Party mode",
        "6": "Holiday on", "7": "Holiday off",
    },
    801: {
        "0": "No HC/storage", "1": "1 A1", "2": "2 A1 + WW", "3": "3 M2",
        "4": "4 M2 + WW", "5": "5 A1 + M2", "6": "6 A1 + M2 + WW",
        "7": "7 M2 + M3", "8": "8 M2 + M3 + WW", "9": "9 A1 + M2 + M3",
        "10": "10 A1 + M2 + M3 + WW",
    },
    865:  {"0": "Inactive", "1": "Active"},
    990:  {"0": "None", "1": "Error manager"},
    7271: {
        "0": "None", "1": "Vitosolic 100", "2": "Vitosolic 200",
        "3": "Solar module SM1", "4": "SM1 with DT2",
    },
    # -- Heat pump enum sensors ------------------------------------------------
    8537: {"0": "Standby", "1": "Reduced", "2": "Normal", "3": "Fixed value"},
    6181: {
        "0": "DHW only", "1": "1 HC", "2": "1 HC + DHW",
        "3": "1 mixer circuit", "4": "1 mixer circuit + DHW",
        "5": "1 HC + 1 mixer circuit", "6": "1 HC + 1 mixer circuit + DHW",
        "7": "2 mixer circuits", "8": "2 mixer circuits + DHW",
        "9": "1 HC + 2 mixer circuits", "10": "1 HC + 2 mixer circuits + DHW",
        "11": "External control",
    },
    6524: {"0": "Present", "1": "Not present"},
    # -- Heat pump select entities ---------------------------------------------
    6976: {
        "0": "None", "1": "Vitosolic 100", "2": "Vitosolic 200",
        "3": "Solar module SM1", "4": "Internal solar control",
    },
    7373: {
        "0": "Off", "1": "DHW only", "2": "Heating/Cooling + DHW",
        "4": "Continuous reduced", "5": "Continuous normal",
        "6": "Normal off", "7": "Cooling only",
    },
}


# ============================================================================
# Binary sensor on_values overrides
# ============================================================================
# Category "running"/"safety"/"bool" defaults to on_values=("1",).
# Add overrides here for attrs where other raw values also mean "on".

_ON_VALUES: dict[int, tuple[str, ...]] = {
    245: ("1", "3"),  # Internal pump: values 1 and 3 both mean "on"
}


# ============================================================================
# Build ATTRIBUTE_REGISTRY from the table + templates + overrides
# ============================================================================

ATTRIBUTE_REGISTRY: dict[int, AttrMeta] = {}

for _id, _name, _enabled, _cat in _TABLE:
    _merged = {**_CATEGORIES[_cat]}
    if _id in _ENUM_MAPS:
        _merged["enum_map"] = _ENUM_MAPS[_id]
    if _id in _ON_VALUES:
        _merged["on_values"] = _ON_VALUES[_id]
    ATTRIBUTE_REGISTRY[_id] = AttrMeta(
        name=_name,
        enabled_by_default=_enabled,
        **_merged,
    )


# ============================================================================
# History sensors (generated — too many for the table)
# ============================================================================

def _add_history(ids: list[int], pattern: str, category: str) -> None:
    """Register a batch of history sensor attributes."""
    tmpl = _CATEGORIES[category]
    for i, attr_id in enumerate(ids, start=1):
        ATTRIBUTE_REGISTRY[attr_id] = AttrMeta(name=pattern.format(i), **tmpl)

# Electrical energy — last year monthly (9847-9858)
_add_history(list(range(9847, 9859)), "Elec. energy last year month {}", "energy_h")
# Electrical energy — this year monthly (9859-9870)
_add_history(list(range(9859, 9871)), "Elec. energy this year month {}", "energy_h")
# Electrical energy — this month daily (9953, 9955-9984; skip 9954)
_add_history([9953] + list(range(9955, 9985)), "Elec. energy this month day {}", "energy_h")
# Electrical energy — last month daily (9985-10015)
_add_history(list(range(9985, 10016)), "Elec. energy last month day {}", "energy_h")
# CO2 savings — last year monthly (9873, 9875-9885; skip 9874)
_add_history([9873] + list(range(9875, 9886)), "CO2 savings last year month {}", "weight_h")
# CO2 savings — this year monthly (9886-9897)
_add_history(list(range(9886, 9898)), "CO2 savings this year month {}", "weight_h")
# CO2 savings — this month daily (10016-10046)
_add_history(list(range(10016, 10047)), "CO2 savings this month day {}", "weight_h")
# CO2 savings — last month daily (10047-10077)
_add_history(list(range(10047, 10078)), "CO2 savings last month day {}", "weight_h")

# Clean up builder variables
del _id, _name, _enabled, _cat, _merged


# ============================================================================
# Climate action resolvers
# ============================================================================
# Each function maps (requested_mode, current_mode, burner_state) raw strings
# to an HVACAction.  Co-located with the enum maps that define the raw values.


def _boiler_action(
    requested: str | None,
    current_mode: str | None,
    burner: str | None,
) -> HVACAction | None:
    """Resolve HVAC action for boiler / fuel cell devices.

    Raw values — see enum maps for attrs 92 and 708:
      requested "1" = DHW only,  current_mode "0" = Standby
    """
    # DHW-only: burner fires for hot water
    if requested == "1":
        return HVACAction.DRYING if burner == "1" else HVACAction.IDLE
    # Standby
    if current_mode == "0":
        return HVACAction.OFF
    # Normal operation
    if burner == "1":
        return HVACAction.HEATING
    if burner is not None:
        return HVACAction.IDLE
    return None


def _heat_pump_action(
    requested: str | None,
    current_mode: str | None,
    burner: str | None,
) -> HVACAction | None:
    """Resolve HVAC action for heat pump devices.

    Raw values — see enum maps for attrs 7373 and 8537:
      requested "1" = DHW only,  "7" = Cooling only
      current_mode "0" = Standby
    """
    # DHW-only: compressor fires for hot water
    if requested == "1":
        return HVACAction.DRYING if burner == "1" else HVACAction.IDLE
    # Standby
    if current_mode == "0":
        return HVACAction.OFF
    # Cooling-only: compressor runs for cooling
    if requested == "7":
        if burner == "1":
            return HVACAction.COOLING
        if burner is not None:
            return HVACAction.IDLE
        return None
    # Normal operation (heating modes)
    if burner == "1":
        return HVACAction.HEATING
    if burner is not None:
        return HVACAction.IDLE
    return None


# ============================================================================
# Climate configuration
# ============================================================================

CLIMATE_CONFIGS: list[ClimateMeta] = [
    # Boilers (Vitodens, Vitovalor, etc.)
    ClimateMeta(
        current_temp_attr=5367,     # Indoor temperature
        target_temp_attr=82,        # Room temperature setpoint (RW)
        operating_mode_attr=92,     # Operating mode (RW, enum 0-4)
        resolve_action=_boiler_action,
        current_mode_attr=708,      # Current operating mode (RO)
        burner_state_attr=600,      # Burner state (RO)
        eco_mode_attr=7852,         # Energy saving mode (RW)
        party_mode_attr=7855,       # Party mode (RW)
        hvac_to_vitotrol={
            HVACMode.OFF: "0",         # Abschalt
            HVACMode.DRY: "1",         # Nur WW (DHW only)
            HVACMode.AUTO: "2",        # Heizen + WW (schedule-driven)
        },
        vitotrol_to_hvac={
            "0": HVACMode.OFF,         # Abschalt
            "1": HVACMode.DRY,         # Nur WW (DHW only)
            "2": HVACMode.AUTO,        # Heizen + WW
            "3": HVACMode.AUTO,        # Dauernd Reduziert (still heating)
            "4": HVACMode.AUTO,        # Dauernd Normal (still heating)
        },
    ),
    # Heat pumps (VT 200, Vitocal, etc.)
    ClimateMeta(
        current_temp_attr=7299,     # Indoor temperature (temp_rts_r)
        target_temp_attr=6369,      # Room temperature setpoint (RW)
        operating_mode_attr=7373,   # Operating mode (RW, enum)
        resolve_action=_heat_pump_action,
        current_mode_attr=8537,     # Current operating mode (RO)
        burner_state_attr=6710,     # Compressor state (RO)
        eco_mode_attr=8062,         # Energy saving mode (RW)
        party_mode_attr=8059,       # Party mode (RW)
        hvac_to_vitotrol={
            HVACMode.OFF: "0",         # Abschaltbetrieb
            HVACMode.DRY: "1",         # Nur WW (DHW only)
            HVACMode.AUTO: "2",        # Heizen/Kühlen/WW (schedule-driven)
            HVACMode.COOL: "7",        # Nur Kühlen (Cooling only)
        },
        vitotrol_to_hvac={
            "0": HVACMode.OFF,         # Abschaltbetrieb
            "1": HVACMode.DRY,         # Nur WW (DHW only)
            "2": HVACMode.AUTO,        # Heizen/Kühlen/WW
            "4": HVACMode.AUTO,        # Dauernd Reduziert (still heating)
            "5": HVACMode.AUTO,        # Dauernd Normal (still heating)
            "6": HVACMode.OFF,         # Normal Abschalt (scheduled off)
            "7": HVACMode.COOL,        # Nur Kühlen (Cooling only)
        },
    ),
]
