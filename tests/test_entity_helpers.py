"""Unit tests for entity.py helper functions (no HA setup required)."""
from __future__ import annotations

import pytest

from custom_components.vitotrol.api import AttributeTypeInfo
from custom_components.vitotrol.entity import (
    _group_prefix,
    _infer_numeric_meta,
    _is_binary_enum,
    entity_key_for_attr,
    infer_unknown_metadata,
)


def _info(**kwargs) -> AttributeTypeInfo:
    """Build a minimal AttributeTypeInfo with defaults for unspecified fields."""
    defaults = dict(
        attr_id=9999,
        name="Test_Attr",
        type="Double",
        type_value="3",
        min_value=None,
        max_value=None,
        unit=None,
        group=None,
        heating_circuit_id=None,
        factory_default=None,
        readable=True,
        writable=False,
        enum_values=None,
    )
    defaults.update(kwargs)
    return AttributeTypeInfo(**defaults)


# ---------------------------------------------------------------------------
# entity_key_for_attr
# ---------------------------------------------------------------------------

def test_entity_key_unknown_attr():
    """Unknown attr (meta=None) yields attr_{id}."""
    assert entity_key_for_attr(9999, None) == "attr_9999"


# ---------------------------------------------------------------------------
# _is_binary_enum
# ---------------------------------------------------------------------------

def test_is_binary_enum_aus_ein():
    info = _info(enum_values={0: "Aus", 1: "Ein"})
    assert _is_binary_enum(info) is True


def test_is_binary_enum_aktiv_inaktiv():
    info = _info(enum_values={0: "Inaktiv", 1: "Aktiv"})
    assert _is_binary_enum(info) is True


def test_is_binary_enum_more_than_two_values():
    info = _info(enum_values={0: "Aus", 1: "Ein", 2: "Auto"})
    assert _is_binary_enum(info) is False


def test_is_binary_enum_no_enum_values():
    info = _info(enum_values=None)
    assert _is_binary_enum(info) is False


def test_is_binary_enum_non_binary_labels():
    info = _info(enum_values={0: "Off", 1: "Heating", 2: "DHW"})
    assert _is_binary_enum(info) is False


# ---------------------------------------------------------------------------
# _group_prefix
# ---------------------------------------------------------------------------

def test_group_prefix_with_tilde():
    assert _group_prefix("Zone~HC2") == "HC2"


def test_group_prefix_no_tilde():
    assert _group_prefix("Allgemein") == ""


def test_group_prefix_none():
    assert _group_prefix(None) == ""


def test_group_prefix_empty():
    assert _group_prefix("") == ""


# ---------------------------------------------------------------------------
# _infer_numeric_meta — name-based heuristics
# ---------------------------------------------------------------------------

def test_infer_numeric_temp_prefix():
    dc, unit, sc, prec = _infer_numeric_meta("Temp_Aussen")
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import UnitOfTemperature
    assert dc == SensorDeviceClass.TEMPERATURE
    assert unit == UnitOfTemperature.CELSIUS
    assert sc == SensorStateClass.MEASUREMENT
    assert prec == 1


def test_infer_numeric_brennerstunden():
    dc, unit, sc, prec = _infer_numeric_meta("Anzahl_Brennerstunden_Abgasanlage")
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import UnitOfTime
    assert dc == SensorDeviceClass.DURATION
    assert unit == UnitOfTime.HOURS
    assert sc == SensorStateClass.TOTAL_INCREASING


def test_infer_numeric_brennerstart():
    from homeassistant.components.sensor import SensorStateClass
    dc, unit, sc, prec = _infer_numeric_meta("Anzahl_Brennerstart_Abgas")
    assert dc is None
    assert sc == SensorStateClass.TOTAL_INCREASING


def test_infer_numeric_modulation():
    from homeassistant.components.sensor import SensorStateClass
    from homeassistant.const import PERCENTAGE
    dc, unit, sc, prec = _infer_numeric_meta("Info_Brenner_Modulation")
    assert unit == PERCENTAGE
    assert sc == SensorStateClass.MEASUREMENT


def test_infer_numeric_historie_eee():
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import UnitOfEnergy
    dc, unit, sc, prec = _infer_numeric_meta("Info_Historie_EEE_Jan")
    assert dc == SensorDeviceClass.ENERGY
    assert unit == UnitOfEnergy.KILO_WATT_HOUR


def test_infer_numeric_historie_co2():
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import UnitOfMass
    dc, unit, sc, prec = _infer_numeric_meta("Info_Historie_CO2_Jan")
    assert dc == SensorDeviceClass.WEIGHT
    assert unit == UnitOfMass.KILOGRAMS


def test_infer_numeric_energie():
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import UnitOfEnergy
    dc, unit, sc, prec = _infer_numeric_meta("Info_Energie_gesamt")
    assert dc == SensorDeviceClass.ENERGY
    assert unit == UnitOfEnergy.KILO_WATT_HOUR
    assert sc == SensorStateClass.TOTAL_INCREASING


def test_infer_numeric_leistung():
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import UnitOfPower
    dc, unit, sc, prec = _infer_numeric_meta("Info_Leistung_Heiz")
    assert dc == SensorDeviceClass.POWER
    assert unit == UnitOfPower.WATT


def test_infer_numeric_verbrauch():
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import UnitOfVolume
    dc, unit, sc, prec = _infer_numeric_meta("Info_Verbrauch_Gas")
    assert dc == SensorDeviceClass.GAS
    assert unit == UnitOfVolume.CUBIC_METERS


def test_infer_numeric_einsparung():
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import UnitOfMass
    dc, unit, sc, prec = _infer_numeric_meta("Info_Einsparung_CO2")
    assert dc == SensorDeviceClass.WEIGHT
    assert unit == UnitOfMass.KILOGRAMS


def test_infer_numeric_verhaeltnis():
    from homeassistant.const import PERCENTAGE
    dc, unit, sc, prec = _infer_numeric_meta("Info_Verhaeltnis_Solar")
    assert unit == PERCENTAGE


def test_infer_numeric_solarstunden():
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import UnitOfTime
    dc, unit, sc, prec = _infer_numeric_meta("Solarstunden_Gesamt")
    assert dc == SensorDeviceClass.DURATION
    assert unit == UnitOfTime.HOURS


def test_infer_numeric_solarenergie():
    from homeassistant.components.sensor import SensorDeviceClass
    from homeassistant.const import UnitOfEnergy
    dc, unit, sc, prec = _infer_numeric_meta("Solarenergie_Gesamt")
    assert dc == SensorDeviceClass.ENERGY
    assert unit == UnitOfEnergy.KILO_WATT_HOUR


def test_infer_numeric_solarertrag():
    from homeassistant.components.sensor import SensorDeviceClass
    from homeassistant.const import UnitOfEnergy
    dc, unit, sc, prec = _infer_numeric_meta("Solarertrag_Tag")
    assert dc == SensorDeviceClass.ENERGY
    assert unit == UnitOfEnergy.WATT_HOUR


def test_infer_numeric_unknown_name():
    dc, unit, sc, prec = _infer_numeric_meta("Some_Unknown_Attr")
    from homeassistant.components.sensor import SensorStateClass
    assert dc is None
    assert unit is None
    assert sc == SensorStateClass.MEASUREMENT


# ---------------------------------------------------------------------------
# infer_unknown_metadata — all platform branches
# ---------------------------------------------------------------------------

def test_infer_date_type():
    info = _info(type="Date")
    result = infer_unknown_metadata(info)
    assert result.platform == "sensor"


def test_infer_circuit_time():
    info = _info(type="CircuitTime")
    result = infer_unknown_metadata(info)
    assert result.platform is None


def test_infer_enum_binary_writable_is_switch():
    info = _info(type="ENUM", writable=True, enum_values={0: "Aus", 1: "Ein"})
    result = infer_unknown_metadata(info)
    assert result.platform == "switch"


def test_infer_enum_binary_readonly_is_binary_sensor():
    info = _info(type="ENUM", writable=False, enum_values={0: "Aus", 1: "Ein"})
    result = infer_unknown_metadata(info)
    assert result.platform == "binary_sensor"


def test_infer_enum_multi_writable_is_select():
    info = _info(
        type="ENUM", writable=True,
        enum_values={0: "Off", 1: "On", 2: "Auto"}
    )
    result = infer_unknown_metadata(info)
    assert result.platform == "select"


def test_infer_enum_multi_readonly_is_sensor():
    info = _info(
        type="ENUM", writable=False,
        enum_values={0: "Off", 1: "On", 2: "Auto"}
    )
    result = infer_unknown_metadata(info)
    assert result.platform == "sensor"


def test_infer_double_writable_no_enum_is_number():
    info = _info(type="Double", writable=True, enum_values=None)
    result = infer_unknown_metadata(info)
    assert result.platform == "number"


def test_infer_double_readonly_is_sensor():
    info = _info(type="Double", writable=False, enum_values=None)
    result = infer_unknown_metadata(info)
    assert result.platform == "sensor"


def test_infer_integer_writable_no_enum_is_number():
    info = _info(type="Integer", writable=True, enum_values=None)
    result = infer_unknown_metadata(info)
    assert result.platform == "number"


def test_infer_string_type_is_sensor():
    info = _info(type="String")
    result = infer_unknown_metadata(info)
    assert result.platform == "sensor"


def test_infer_display_name_uses_group_prefix():
    info = _info(name="Temp", group="Zone~HC2", type="Double")
    result = infer_unknown_metadata(info)
    assert result.display_name == "HC2: Temp"


def test_infer_display_name_no_prefix():
    info = _info(name="Temp_Aussen", group="Allgemein", type="Double")
    result = infer_unknown_metadata(info)
    assert result.display_name == "Temp_Aussen"
