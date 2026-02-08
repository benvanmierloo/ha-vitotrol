#!/usr/bin/env python3
"""Standalone discovery script for the Viessmann Vitotrol SOAP API.

Logs in, discovers devices, calls GetTypeInfo, and prints all available
attributes with their metadata (unit, type, min/max, RW flags, enums).

With --values, also fetches current cached values via GetData.

Usage:
    python scripts/discover.py --user YOUR_EMAIL --password YOUR_PASSWORD
    python scripts/discover.py --user YOUR_EMAIL --password YOUR_PASSWORD --values

Or set environment variables:
    VITOTROL_USER=... VITOTROL_PASSWORD=... python scripts/discover.py --values
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from xml.etree import ElementTree

import aiohttp
from defusedxml.ElementTree import fromstring as _safe_xml_fromstring

# SOAP constants (duplicated to keep this script standalone)
API_ENDPOINT = (
    "https://vitotrolapp.viessmann-climatesolutions.com"
    "/app_vitodata/VIIWebService-1.16.0.0/iPhoneWebService.asmx"
)
API_NAMESPACE = "http://www.e-controlnet.de/services/vii/"
APP_ID = "prod"
APP_VERSION = "4.3.1"
APP_OS = "Android"

_NS_RE = re.compile(r"\{[^}]+\}")

_SOAP_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
    ' xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
    f' xmlns="{API_NAMESPACE}">'
    "<soap:Body>{body}</soap:Body>"
    "</soap:Envelope>"
)


def _strip_ns(element: ElementTree.Element) -> None:
    element.tag = _NS_RE.sub("", element.tag)
    for child in element:
        _strip_ns(child)


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _find_text(el: ElementTree.Element, tag: str) -> str:
    child = el.find(f".//{tag}")
    if child is None or child.text is None:
        raise RuntimeError(f"Missing <{tag}>")
    return child.text


def _find_text_opt(el: ElementTree.Element, tag: str) -> str | None:
    child = el.find(f".//{tag}")
    return child.text if child is not None else None


async def soap_request(
    session: aiohttp.ClientSession,
    cookies: dict[str, str],
    action: str,
    body: str,
    *,
    store_cookies: bool = False,
) -> ElementTree.Element:
    envelope = _SOAP_ENVELOPE.format(body=body)
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"{API_NAMESPACE}{action}",
    }
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

    async with session.post(
        API_ENDPOINT,
        data=envelope.encode("utf-8"),
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        if store_cookies:
            for cookie in resp.cookies.values():
                cookies[cookie.key] = cookie.value
        resp_text = await resp.text()

    root = _safe_xml_fromstring(resp_text)
    _strip_ns(root)

    result_el = root.find(f".//{action}Result")
    if result_el is None:
        raise RuntimeError(f"Missing {action}Result in response")

    ergebnis = result_el.find("Ergebnis")
    if ergebnis is None or int(ergebnis.text or "-1") != 0:
        error_text = _find_text_opt(result_el, "ErgebnisText") or "Unknown"
        raise RuntimeError(f"{action} failed: {error_text}")

    return result_el


async def get_data(
    session: aiohttp.ClientSession,
    cookies: dict[str, str],
    loc_id: int,
    dev_id: int,
    attr_ids: list[int],
) -> dict[int, str]:
    """Fetch cached attribute values via GetData. Batches if needed."""
    all_values: dict[int, str] = {}
    batch_size = 50  # conservative batch size to avoid oversized requests

    for i in range(0, len(attr_ids), batch_size):
        batch = attr_ids[i : i + batch_size]
        dp_list = "".join(f"<int>{aid}</int>" for aid in batch)
        body = (
            "<GetData>"
            f"<AnlageId>{loc_id}</AnlageId>"
            f"<GeraetId>{dev_id}</GeraetId>"
            f"<DatenpunktIds>{dp_list}</DatenpunktIds>"
            "</GetData>"
        )
        try:
            root = await soap_request(session, cookies, "GetData", body)
            for dp in root.iter("WerteListe"):
                attr_id = int(_find_text(dp, "DatenpunktId"))
                value = _find_text(dp, "Wert")
                all_values[attr_id] = value
        except RuntimeError as err:
            print(f"  Warning: GetData batch {i//batch_size + 1} failed: {err}")

    return all_values


async def run(username: str, password: str, *, fetch_values: bool = False) -> None:
    cookies: dict[str, str] = {}

    async with aiohttp.ClientSession() as session:
        # Login
        print("Logging in...")
        await soap_request(
            session,
            cookies,
            "Login",
            (
                "<Login>"
                f"<AppId>{APP_ID}</AppId>"
                f"<AppVersion>{APP_VERSION}</AppVersion>"
                f"<Betriebssystem>{APP_OS}</Betriebssystem>"
                f"<Benutzer>{_xml_escape(username)}</Benutzer>"
                f"<Passwort>{_xml_escape(password)}</Passwort>"
                "</Login>"
            ),
            store_cookies=True,
        )
        print("Login OK\n")

        # Discover devices
        print("Discovering devices...")
        dev_root = await soap_request(session, cookies, "GetDevices", "<GetDevices />")

        devices = []
        for anlage in dev_root.iter("AnlageV2"):
            loc_id = int(_find_text(anlage, "AnlageId"))
            loc_name = _find_text(anlage, "AnlageName")
            for geraet in anlage.iter("GeraetV2"):
                dev_id = int(_find_text(geraet, "GeraetId"))
                dev_name = _find_text(geraet, "GeraetName")
                connected = _find_text(geraet, "IstVerbunden") == "true"
                devices.append((loc_id, loc_name, dev_id, dev_name, connected))

        if not devices:
            print("No devices found!")
            return

        for loc_id, loc_name, dev_id, dev_name, connected in devices:
            print(f"  Location: {loc_name} (ID={loc_id})")
            print(f"  Device:   {dev_name} (ID={dev_id}, connected={connected})")
            print()

        # GetTypeInfo for each device
        for loc_id, loc_name, dev_id, dev_name, _ in devices:
            print(f"{'='*80}")
            print(f"GetTypeInfo for {dev_name} (device={dev_id}, location={loc_id})")
            print(f"{'='*80}\n")

            type_root = await soap_request(
                session,
                cookies,
                "GetTypeInfo",
                (
                    "<GetTypeInfo>"
                    f"<AnlageId>{loc_id}</AnlageId>"
                    f"<GeraetId>{dev_id}</GeraetId>"
                    "</GetTypeInfo>"
                ),
            )

            # Collect all entries
            base_entries: dict[int, dict] = {}
            enum_entries: dict[int, dict[int, str]] = {}

            for dp in type_root.iter("DatenpunktTypInfo"):
                raw_id = _find_text(dp, "DatenpunktId")

                if "-" in raw_id:
                    parts = raw_id.split("-", 1)
                    attr_id = int(parts[0])
                    index = int(parts[1])
                    label = _find_text_opt(dp, "MinimalWert") or str(index)
                    enum_entries.setdefault(attr_id, {})[index] = label
                    continue

                attr_id = int(raw_id)
                base_entries[attr_id] = {
                    "id": attr_id,
                    "name": _find_text_opt(dp, "DatenpunktName") or "",
                    "type": _find_text_opt(dp, "DatenpunktTyp") or "",
                    "min": _find_text_opt(dp, "MinimalWert") or "",
                    "max": _find_text_opt(dp, "MaximalWert") or "",
                    "unit": _find_text_opt(dp, "EinheitBezeichnung") or "",
                    "group": _find_text_opt(dp, "DatenpunktGruppe") or "",
                    "hc_id": _find_text_opt(dp, "HeizkreisId") or "",
                    "default": _find_text_opt(dp, "Auslieferungswert") or "",
                    "readable": _find_text_opt(dp, "IstLesbar") == "true",
                    "writable": _find_text_opt(dp, "IstSchreibbar") == "true",
                }

            # Attach enums
            for attr_id, vals in enum_entries.items():
                if attr_id in base_entries:
                    base_entries[attr_id]["enums"] = vals

            # Optionally fetch current values
            values: dict[int, str] = {}
            if fetch_values:
                readable_ids = [
                    aid for aid, e in base_entries.items()
                    if e["readable"] and e["type"] not in ("CircuitTime",)
                ]
                print(f"Fetching values for {len(readable_ids)} readable attributes...")
                values = await get_data(session, cookies, loc_id, dev_id, readable_ids)
                print(f"Got {len(values)} values\n")

            # Collect unique units for summary
            units: set[str] = set()

            # Print table
            val_header = " Value" + " " * 15 if fetch_values else ""
            print(
                f"{'ID':>6}  {'Name':<40} {'Type':<12} {'Unit':<8} "
                f"{'Min':<10} {'Max':<10} {'RO/RW':<5}{val_header}"
            )
            print("-" * (100 + (20 if fetch_values else 0)))

            for attr_id in sorted(base_entries):
                e = base_entries[attr_id]
                rw = "RW" if e["writable"] else "RO"
                if not e["readable"] and not e["writable"]:
                    rw = "--"
                elif not e["readable"]:
                    rw = "WO"

                if e["unit"]:
                    units.add(e["unit"])

                val_col = ""
                if fetch_values and attr_id in values:
                    val_col = f" {values[attr_id]}"

                print(
                    f"{e['id']:>6}  {e['name']:<40} {e['type']:<12} {e['unit']:<8} "
                    f"{e['min']:<10} {e['max']:<10} {rw:<5}{val_col}"
                )

                if "enums" in e:
                    for idx in sorted(e["enums"]):
                        print(f"        enum {idx} = {e['enums'][idx]}")

            print(f"\nTotal attributes: {len(base_entries)}")
            if fetch_values:
                print(f"Values retrieved: {len(values)}")

            # Unit summary
            if units:
                print(f"\nUnique units found: {sorted(units)}")
            else:
                print("\nNo units returned by API (EinheitBezeichnung empty for all attributes)")

            print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Vitotrol device discovery")
    parser.add_argument("--user", default=os.environ.get("VITOTROL_USER"), help="Vitotrol username (or VITOTROL_USER env)")
    parser.add_argument("--password", default=os.environ.get("VITOTROL_PASSWORD"), help="Vitotrol password (or VITOTROL_PASSWORD env)")
    parser.add_argument("--values", action="store_true", help="Also fetch current cached values via GetData")
    args = parser.parse_args()

    if not args.user or not args.password:
        print("Error: provide --user/--password or set VITOTROL_USER/VITOTROL_PASSWORD env vars", file=sys.stderr)
        sys.exit(1)

    asyncio.run(run(args.user, args.password, fetch_values=args.values))


if __name__ == "__main__":
    main()
