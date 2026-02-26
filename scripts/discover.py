#!/usr/bin/env python3
"""Standalone discovery script for the Viessmann Vitotrol SOAP API.

Logs in, discovers devices, calls GetTypeInfo, and prints all available
attributes with their metadata (unit, type, min/max, RW flags, enums).

With --values, also fetches current cached values via GetData.
With --raw-xml, dumps the raw GetTypeInfo XML for offline analysis.
With --json, outputs structured JSON instead of a table.

Usage:
    python scripts/discover.py --user YOUR_EMAIL --password YOUR_PASSWORD
    python scripts/discover.py --user YOUR_EMAIL --password YOUR_PASSWORD --values
    python scripts/discover.py --user YOUR_EMAIL --password YOUR_PASSWORD --json > dump.json

Or set environment variables:
    VITOTROL_USER=... VITOTROL_PASSWORD=... python scripts/discover.py --values
"""

from __future__ import annotations

import argparse
import asyncio
import json
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


async def run(
    username: str,
    password: str,
    *,
    fetch_values: bool = False,
    output_json: bool = False,
    dump_raw_xml: bool = False,
) -> None:
    cookies: dict[str, str] = {}
    json_output: list[dict] = []

    async with aiohttp.ClientSession() as session:
        # Login
        print("Logging in...", file=sys.stderr)
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
        print("Login OK\n", file=sys.stderr)

        # Discover devices
        print("Discovering devices...", file=sys.stderr)
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
            print("No devices found!", file=sys.stderr)
            return

        for loc_id, loc_name, dev_id, dev_name, connected in devices:
            print(f"  Location: {loc_name} (ID={loc_id})", file=sys.stderr)
            print(f"  Device:   {dev_name} (ID={dev_id}, connected={connected})", file=sys.stderr)
            print(file=sys.stderr)

        # GetTypeInfo for each device
        for loc_id, loc_name, dev_id, dev_name, _ in devices:
            if not output_json:
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

            # Optionally dump raw XML
            if dump_raw_xml:
                type_info_list = type_root.find(".//TypeInfoListe")
                target = type_info_list if type_info_list is not None else type_root
                raw_xml = ElementTree.tostring(target, encoding="unicode")
                xml_file = f"typeinfo_{dev_id}.xml"
                with open(xml_file, "w") as f:
                    f.write(raw_xml)
                print(f"  Raw XML dumped to {xml_file}", file=sys.stderr)

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
                    "type_value": _find_text_opt(dp, "DatenpunktTypWert") or "",
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
                print(f"Fetching values for {len(readable_ids)} readable attributes...", file=sys.stderr)
                values = await get_data(session, cookies, loc_id, dev_id, readable_ids)
                print(f"Got {len(values)} values\n", file=sys.stderr)

            # JSON output mode
            if output_json:
                device_data = {
                    "device_name": dev_name,
                    "device_id": dev_id,
                    "location_name": loc_name,
                    "location_id": loc_id,
                    "attributes": {},
                }
                for attr_id in sorted(base_entries):
                    e = base_entries[attr_id]
                    entry: dict = {
                        "name": e["name"],
                        "type": e["type"],
                        "type_value": e["type_value"],
                        "min": e["min"],
                        "max": e["max"],
                        "unit": e["unit"],
                        "group": e["group"],
                        "heating_circuit_id": e["hc_id"],
                        "factory_default": e["default"],
                        "readable": e["readable"],
                        "writable": e["writable"],
                    }
                    if "enums" in e:
                        entry["enum_values"] = {
                            str(k): v for k, v in sorted(e["enums"].items())
                        }
                    if attr_id in values:
                        entry["current_value"] = values[attr_id]
                    device_data["attributes"][str(attr_id)] = entry
                json_output.append(device_data)
                continue

            # Collect unique units and type mappings for summary
            units: set[str] = set()
            type_mapping: dict[str, set[str]] = {}  # type_value -> {type_str, ...}
            groups: set[str] = set()

            # Print table
            val_header = " Value" + " " * 15 if fetch_values else ""
            print(
                f"{'ID':>6}  {'Name':<40} {'Type':<12} {'TV':>3} {'Unit':<8} "
                f"{'Min':<10} {'Max':<10} {'RO/RW':<5} {'HC':>2} {'Group':<16} {'Default':<10}{val_header}"
            )
            print("-" * (130 + (20 if fetch_values else 0)))

            for attr_id in sorted(base_entries):
                e = base_entries[attr_id]
                rw = "RW" if e["writable"] else "RO"
                if not e["readable"] and not e["writable"]:
                    rw = "--"
                elif not e["readable"]:
                    rw = "WO"

                if e["unit"]:
                    units.add(e["unit"])
                if e["group"]:
                    groups.add(e["group"])
                if e["type_value"]:
                    type_mapping.setdefault(e["type_value"], set()).add(e["type"])

                val_col = ""
                if fetch_values and attr_id in values:
                    val_col = f" {values[attr_id]}"

                print(
                    f"{e['id']:>6}  {e['name']:<40} {e['type']:<12} {e['type_value']:>3} {e['unit']:<8} "
                    f"{e['min']:<10} {e['max']:<10} {rw:<5} {e['hc_id']:>2} {e['group']:<16} {e['default']:<10}{val_col}"
                )

                if "enums" in e:
                    for idx in sorted(e["enums"]):
                        print(f"        enum {idx} = {e['enums'][idx]}")

            print(f"\nTotal attributes: {len(base_entries)}")
            if fetch_values:
                print(f"Values retrieved: {len(values)}")

            # Type value mapping summary
            if type_mapping:
                print(f"\nDatenpunktTypWert -> DatenpunktTyp mapping:")
                for tv in sorted(type_mapping, key=lambda x: int(x) if x.isdigit() else 999):
                    types = ", ".join(sorted(type_mapping[tv]))
                    count = sum(
                        1 for e in base_entries.values() if e["type_value"] == tv
                    )
                    print(f"  {tv:>3} -> {types} ({count} attrs)")

            # Unit summary
            if units:
                print(f"\nUnique units: {sorted(units)}")

            # Group summary
            if groups:
                print(f"\nUnique groups: {sorted(groups)}")

            print()

        # Final JSON output
        if output_json:
            print(json.dumps(json_output, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vitotrol device discovery — scan the SOAP API for all attributes"
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("VITOTROL_USER"),
        help="Vitotrol username (or VITOTROL_USER env)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("VITOTROL_PASSWORD"),
        help="Vitotrol password (or VITOTROL_PASSWORD env)",
    )
    parser.add_argument(
        "--values",
        action="store_true",
        help="Also fetch current cached values via GetData",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON (pipe to file with > dump.json)",
    )
    parser.add_argument(
        "--raw-xml",
        action="store_true",
        help="Dump raw GetTypeInfo XML per device to typeinfo_<id>.xml",
    )
    args = parser.parse_args()

    if not args.user or not args.password:
        print(
            "Error: provide --user/--password or set VITOTROL_USER/VITOTROL_PASSWORD env vars",
            file=sys.stderr,
        )
        sys.exit(1)

    asyncio.run(
        run(
            args.user,
            args.password,
            fetch_values=args.values,
            output_json=args.json,
            dump_raw_xml=args.raw_xml,
        )
    )


if __name__ == "__main__":
    main()
