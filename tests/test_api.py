"""Tests for api.py module-level helpers."""
from __future__ import annotations

import pytest

from custom_components.vitotrol.api import _format_wire_value


class TestFormatWireValue:
    """Tests for the _format_wire_value helper."""

    def test_whole_number_float_strips_decimal(self):
        """20.0 (whole number float) should become '20'."""
        assert _format_wire_value("20.0") == "20"

    def test_decimal_fraction_preserved(self):
        """20.5 (meaningful decimal) should remain '20.5'."""
        assert _format_wire_value("20.5") == "20.5"

    def test_integer_passthrough(self):
        """'20' (no decimal point) should pass through unchanged."""
        assert _format_wire_value("20") == "20"

    def test_negative_whole_number_strips_decimal(self):
        """'-5.0' (negative whole number float) should become '-5'."""
        assert _format_wire_value("-5.0") == "-5"

    def test_small_decimal_preserved(self):
        """'0.5' (fractional below 1) should remain '0.5'."""
        assert _format_wire_value("0.5") == "0.5"

    def test_large_whole_number_strips_decimal(self):
        """'100.0' (large whole number float) should become '100'."""
        assert _format_wire_value("100.0") == "100"
