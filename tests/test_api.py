"""Tests for api.py module-level helpers."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from xml.etree import ElementTree

import pytest

from custom_components.vitotrol.api import VitotrolAPI, _format_wire_value


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


# ---------------------------------------------------------------------------
# get_type_info malformed enum ID handling (TEST-03)
# ---------------------------------------------------------------------------

def _make_get_type_info_response(entries: list[tuple[str, str | None]]) -> ElementTree.Element:
    """Build a minimal GetTypeInfoResult XML element with the given DatenpunktId entries.

    Each entry is a (DatenpunktId, MinimalWert|None) tuple.
    For base entries, MinimalWert is the readable flag; for enum entries it is the label.
    This helper only populates the fields tested here.
    """
    result_el = ElementTree.fromstring("<GetTypeInfoResult><Ergebnis>0</Ergebnis><TypeInfoListe /></GetTypeInfoResult>")
    type_info_liste = result_el.find(".//TypeInfoListe")
    assert type_info_liste is not None

    for dp_id, minimal_wert in entries:
        dp = ElementTree.SubElement(type_info_liste, "DatenpunktTypInfo")
        id_el = ElementTree.SubElement(dp, "DatenpunktId")
        id_el.text = dp_id
        # Provide minimal fields so base entries parse without error
        for tag, value in [
            ("DatenpunktName", "Test"),
            ("DatenpunktTyp", "ENUM"),
            ("DatenpunktTypWert", "1"),
            ("MaximalWert", None),
            ("EinheitBezeichnung", None),
            ("DatenpunktGruppe", "Test"),
            ("HeizkreisId", None),
            ("Auslieferungswert", None),
            ("IstLesbar", "true"),
            ("IstSchreibbar", "true"),
        ]:
            el = ElementTree.SubElement(dp, tag)
            el.text = value
        min_el = ElementTree.SubElement(dp, "MinimalWert")
        min_el.text = minimal_wert

    return result_el


async def test_get_type_info_skips_malformed_enum_id() -> None:
    """get_type_info does not crash when an enum sub-ID is not a valid integer."""
    import aiohttp

    # Build a response XML with:
    #   - base entry "92" (valid)
    #   - enum entry "92-0" (valid, label "Off")
    #   - enum entry "92-abc" (malformed — sub-ID is not an integer)
    response_el = _make_get_type_info_response([
        ("92", None),       # base entry (MinimalWert unused for base)
        ("92-0", "Off"),    # valid enum entry
        ("92-abc", "Bad"),  # malformed: should be skipped
    ])

    from custom_components.vitotrol.api import VitotrolDevice

    fake_device = VitotrolDevice(
        device_id=1001,
        device_name="Test",
        location_id=2001,
        location_name="Home",
        has_error=False,
        is_connected=True,
    )

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    api = VitotrolAPI("user", "pass", mock_session)

    # Patch _send_request to return our controlled XML without real HTTP
    with patch.object(api, "_send_request", AsyncMock(return_value=response_el)):
        catalog = await api.get_type_info(fake_device)

    # Parsing should succeed without raising
    assert 92 in catalog

    # The valid enum entry "92-0" should be present
    assert catalog[92].enum_values is not None
    assert 0 in catalog[92].enum_values
    assert catalog[92].enum_values[0] == "Off"

    # The malformed entry "92-abc" should have been silently skipped
    # (no "abc" key in enum_values)
    assert "abc" not in catalog[92].enum_values
