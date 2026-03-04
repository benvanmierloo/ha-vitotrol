"""Unit tests for attributes helper functions."""
from __future__ import annotations

import pytest
from homeassistant.components.climate import HVACAction

from custom_components.vitotrol.attributes import _boiler_action, _heat_pump_action


# ---------------------------------------------------------------------------
# _boiler_action
# ---------------------------------------------------------------------------

def test_boiler_action_dhw_burner_firing():
    """requested=1 (DHW only) + burner=1 → DRYING (heating water)."""
    assert _boiler_action("1", None, "1") == HVACAction.DRYING


def test_boiler_action_dhw_burner_idle():
    """requested=1 (DHW only) + burner=0 → IDLE."""
    assert _boiler_action("1", None, "0") == HVACAction.IDLE


def test_boiler_action_standby():
    """current_mode=0 (Standby) → OFF."""
    assert _boiler_action("2", "0", "0") == HVACAction.OFF


def test_boiler_action_heating():
    """Heating mode + burner firing → HEATING."""
    assert _boiler_action("2", "2", "1") == HVACAction.HEATING


def test_boiler_action_idle():
    """Heating mode + burner known but not firing → IDLE."""
    assert _boiler_action("2", "2", "0") == HVACAction.IDLE


def test_boiler_action_no_burner_data():
    """No burner data available → None."""
    assert _boiler_action("2", "2", None) is None


# ---------------------------------------------------------------------------
# _heat_pump_action
# ---------------------------------------------------------------------------

def test_heat_pump_action_dhw_compressor_running():
    """requested=1 (DHW only) + compressor on → DRYING."""
    assert _heat_pump_action("1", None, "1") == HVACAction.DRYING


def test_heat_pump_action_dhw_compressor_idle():
    """requested=1 (DHW only) + compressor off → IDLE."""
    assert _heat_pump_action("1", None, "0") == HVACAction.IDLE


def test_heat_pump_action_standby():
    """current_mode=0 → OFF."""
    assert _heat_pump_action("2", "0", "0") == HVACAction.OFF


def test_heat_pump_action_cooling():
    """requested=7 (Cooling only) + compressor on → COOLING."""
    assert _heat_pump_action("7", "2", "1") == HVACAction.COOLING


def test_heat_pump_action_cooling_idle():
    """requested=7 (Cooling only) + compressor off → IDLE."""
    assert _heat_pump_action("7", "2", "0") == HVACAction.IDLE


def test_heat_pump_action_heating():
    """Heating mode + compressor on → HEATING."""
    assert _heat_pump_action("2", "2", "1") == HVACAction.HEATING


def test_heat_pump_action_heating_idle():
    """Heating mode + compressor known but off → IDLE."""
    assert _heat_pump_action("2", "2", "0") == HVACAction.IDLE


def test_heat_pump_action_no_compressor_data():
    """Cooling mode + no compressor data → None."""
    assert _heat_pump_action("7", "2", None) is None
