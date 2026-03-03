"""Async SOAP client for the Viessmann Vitotrol API.

This module has no Home Assistant dependencies — it relies only on aiohttp
and the Python standard library so it can be tested in isolation.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from xml.etree import ElementTree

import aiohttp
from defusedxml.ElementTree import fromstring as _safe_xml_fromstring

from .const import (
    API_ENDPOINT,
    API_NAMESPACE,
    APP_ID,
    APP_OS,
    APP_VERSION,
    REFRESH_INITIAL_WAIT,
    REFRESH_MIN_WAIT,
    REFRESH_TIMEOUT,
    WRITE_INITIAL_WAIT,
    WRITE_MIN_WAIT,
    WRITE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

_NS_RE = re.compile(r"\{[^}]+\}")

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

_SOAP_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
    ' xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
    f' xmlns="{API_NAMESPACE}">'
    "<soap:Body>{body}</soap:Body>"
    "</soap:Envelope>"
)


class VitotrolError(Exception):
    """General Vitotrol API error."""


class VitotrolAuthError(VitotrolError):
    """Authentication failure."""


@dataclass
class VitotrolDevice:
    """Represents a Viessmann device discovered via GetDevices."""

    location_id: int
    location_name: str
    device_id: int
    device_name: str
    has_error: bool
    is_connected: bool


@dataclass
class AttributeTypeInfo:
    """Metadata for a device attribute from GetTypeInfo."""

    attr_id: int
    name: str
    type: str
    type_value: str
    min_value: str
    max_value: str
    unit: str
    group: str
    heating_circuit_id: str
    factory_default: str
    readable: bool
    writable: bool
    enum_values: dict[int, str] | None = None


def _strip_ns(element: ElementTree.Element) -> None:
    """Remove XML namespace prefixes from tag names in-place."""
    element.tag = _NS_RE.sub("", element.tag)
    for child in element:
        _strip_ns(child)


class VitotrolAPI:
    """Async client for the Viessmann Vitotrol SOAP API."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._cookies: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def login(self) -> None:
        """Authenticate and store the session cookie."""
        body = (
            "<Login>"
            f"<Benutzer>{_xml_escape(self._username)}</Benutzer>"
            f"<Passwort>{_xml_escape(self._password)}</Passwort>"
            f"<Betriebssystem>{APP_OS}</Betriebssystem>"
            f"<AppId>{APP_ID}</AppId>"
            f"<AppVersion>{APP_VERSION}</AppVersion>"
            "</Login>"
        )
        await self._send_request("Login", body, store_cookies=True)
        _LOGGER.debug("Login successful")

    async def get_devices(self) -> list[VitotrolDevice]:
        """Discover all locations and devices under the account."""
        body = "<GetDevices />"
        root = await self._send_request("GetDevices", body)

        devices: list[VitotrolDevice] = []
        for anlage in root.iter("AnlageV2"):
            location_id = int(_find_text(anlage, "AnlageId"))
            location_name = _find_text(anlage, "AnlageName")
            for geraet in anlage.iter("GeraetV2"):
                devices.append(
                    VitotrolDevice(
                        location_id=location_id,
                        location_name=location_name,
                        device_id=int(_find_text(geraet, "GeraetId")),
                        device_name=_find_text(geraet, "GeraetName"),
                        has_error=_find_text(geraet, "HatFehler") == "true",
                        is_connected=_find_text(geraet, "IstVerbunden") == "true",
                    )
                )

        if not devices:
            raise VitotrolError("No devices found under account")

        _LOGGER.debug("Discovered %d device(s)", len(devices))
        return devices

    async def get_type_info(
        self, device: VitotrolDevice
    ) -> dict[int, AttributeTypeInfo]:
        """Get all available datapoint definitions for a device."""
        body = (
            "<GetTypeInfo>"
            f"<AnlageId>{device.location_id}</AnlageId>"
            f"<GeraetId>{device.device_id}</GeraetId>"
            "</GetTypeInfo>"
        )
        root = await self._send_request("GetTypeInfo", body)

        # First pass: collect base entries and enum value entries
        base_entries: dict[int, AttributeTypeInfo] = {}
        enum_values: dict[int, dict[int, str]] = {}

        for dp in root.iter("DatenpunktTypInfo"):
            raw_id = _find_text(dp, "DatenpunktId")

            if "-" in raw_id:
                # Enum value entry: "92-0" -> attr_id=92, index=0
                parts = raw_id.split("-", 1)
                attr_id = int(parts[0])
                index = int(parts[1])
                label = _find_text_opt(dp, "MinimalWert") or str(index)
                enum_values.setdefault(attr_id, {})[index] = label
                continue

            attr_id = int(raw_id)
            base_entries[attr_id] = AttributeTypeInfo(
                attr_id=attr_id,
                name=_find_text_opt(dp, "DatenpunktName") or "",
                type=_find_text_opt(dp, "DatenpunktTyp") or "",
                type_value=_find_text_opt(dp, "DatenpunktTypWert") or "",
                min_value=_find_text_opt(dp, "MinimalWert") or "",
                max_value=_find_text_opt(dp, "MaximalWert") or "",
                unit=_find_text_opt(dp, "EinheitBezeichnung") or "",
                group=_find_text_opt(dp, "DatenpunktGruppe") or "",
                heating_circuit_id=_find_text_opt(dp, "HeizkreisId") or "",
                factory_default=_find_text_opt(dp, "Auslieferungswert") or "",
                readable=_find_text_opt(dp, "IstLesbar") == "true",
                writable=_find_text_opt(dp, "IstSchreibbar") == "true",
            )

        # Second pass: attach enum values to their base entries
        for attr_id, values in enum_values.items():
            if attr_id in base_entries:
                base_entries[attr_id].enum_values = values

        _LOGGER.debug(
            "GetTypeInfo returned %d attributes for device %d",
            len(base_entries),
            device.device_id,
        )
        return base_entries

    async def get_data(
        self, device: VitotrolDevice, attr_ids: list[int]
    ) -> dict[int, str]:
        """Read cached attribute values from the server."""
        dp_list = "".join(
            f"<int>{attr_id}</int>" for attr_id in attr_ids
        )
        body = (
            "<GetData>"
            f"<AnlageId>{device.location_id}</AnlageId>"
            f"<GeraetId>{device.device_id}</GeraetId>"
            f"<DatenpunktIds>{dp_list}</DatenpunktIds>"
            "</GetData>"
        )
        root = await self._send_request("GetData", body)

        data: dict[int, str] = {}
        for dp in root.iter("WerteListe"):
            attr_id = int(_find_text(dp, "DatenpunktId"))
            value = _find_text(dp, "Wert")
            data[attr_id] = value

        return data

    async def refresh_data(
        self, device: VitotrolDevice, attr_ids: list[int]
    ) -> str:
        """Tell the device to upload fresh data. Returns a refresh ID."""
        dp_list = "".join(
            f"<int>{attr_id}</int>" for attr_id in attr_ids
        )
        body = (
            "<RefreshData>"
            f"<AnlageId>{device.location_id}</AnlageId>"
            f"<GeraetId>{device.device_id}</GeraetId>"
            f"<DatenpunktIds>{dp_list}</DatenpunktIds>"
            "</RefreshData>"
        )
        root = await self._send_request("RefreshData", body)
        refresh_id = _find_text(root, "AktualisierungsId")
        _LOGGER.debug("RefreshData started, id=%s", refresh_id)
        return refresh_id

    async def request_refresh_status(self, refresh_id: str) -> int:
        """Poll whether a RefreshData request has completed.

        Returns 0 while pending, non-zero when done.
        """
        body = (
            "<RequestRefreshStatus>"
            f"<AktualisierungsId>{_xml_escape(refresh_id)}</AktualisierungsId>"
            "</RequestRefreshStatus>"
        )
        root = await self._send_request("RequestRefreshStatus", body)
        status = int(_find_text(root, "Status"))
        return status

    async def refresh_data_wait(
        self, device: VitotrolDevice, attr_ids: list[int]
    ) -> None:
        """Fire RefreshData and poll until complete or timeout."""
        refresh_id = await self.refresh_data(device, attr_ids)
        await self._poll_async_status(
            refresh_id,
            self.request_refresh_status,
            "RefreshData",
            REFRESH_INITIAL_WAIT,
            REFRESH_MIN_WAIT,
            REFRESH_TIMEOUT,
        )

    async def write_data(
        self, device: VitotrolDevice, attr_id: int, value: str
    ) -> str:
        """Write a value to the device. Returns a refresh ID."""
        # The API only accepts whole numbers — strip any decimal part.
        wire_value = str(int(float(value))) if "." in value else value
        body = (
            "<WriteData>"
            f"<AnlageId>{device.location_id}</AnlageId>"
            f"<GeraetId>{device.device_id}</GeraetId>"
            f"<DatapointId>{attr_id}</DatapointId>"
            f"<Wert>{_xml_escape(wire_value)}</Wert>"
            "</WriteData>"
        )
        root = await self._send_request("WriteData", body)
        refresh_id = _find_text(root, "AktualisierungsId")
        _LOGGER.debug(
            "WriteData started, attr=%d value=%s id=%s",
            attr_id,
            value,
            refresh_id,
        )
        return refresh_id

    async def request_write_status(self, refresh_id: str) -> int:
        """Poll whether a WriteData request has completed.

        Returns 0 while pending, non-zero when done.
        """
        body = (
            "<RequestWriteStatus>"
            f"<AktualisierungsId>{_xml_escape(refresh_id)}</AktualisierungsId>"
            "</RequestWriteStatus>"
        )
        root = await self._send_request("RequestWriteStatus", body)
        status = int(_find_text(root, "Status"))
        return status

    async def write_data_wait(
        self, device: VitotrolDevice, attr_id: int, value: str
    ) -> None:
        """Fire WriteData and poll until complete or timeout."""
        refresh_id = await self.write_data(device, attr_id, value)
        await self._poll_async_status(
            refresh_id,
            self.request_write_status,
            "WriteData",
            WRITE_INITIAL_WAIT,
            WRITE_MIN_WAIT,
            WRITE_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _poll_async_status(
        self,
        refresh_id: str,
        poll_fn: Callable[[str], Awaitable[int]],
        operation: str,
        initial_wait: float,
        min_wait: float,
        timeout: float,
    ) -> None:
        """Poll an async operation until complete or timeout.

        Status code semantics are not documented in the WSDL (just
        ``unsignedByte``).  The values below are inferred from the Go
        library go-vitotrol's ``waitAsyncStatus`` and are assumptions,
        not verified facts:

        - 0 ...... pending (not yet started)
        - 1, 3 ... in progress
        - 4 ...... success
        - 9 ...... success (observed for some write operations)
        - other ... unexpected / error
        """
        await asyncio.sleep(initial_wait)

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            status = await poll_fn(refresh_id)

            if status >= 4:
                if status not in (4, 9):
                    raise VitotrolError(
                        f"{operation} failed with unexpected status {status}"
                    )
                _LOGGER.debug("%s complete, status=%d", operation, status)
                return

            if loop.time() >= deadline:
                raise VitotrolError(
                    f"{operation} timed out after {timeout}s"
                )

            await asyncio.sleep(min_wait)

    async def _send_request(
        self,
        soap_action: str,
        body: str,
        *,
        store_cookies: bool = False,
    ) -> ElementTree.Element:
        """Build SOAP envelope, POST to the API, parse and validate response."""
        envelope = _SOAP_ENVELOPE.format(body=body)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"{API_NAMESPACE}{soap_action}",
        }
        if self._cookies:
            headers["Cookie"] = "; ".join(
                f"{k}={v}" for k, v in self._cookies.items()
            )

        _LOGGER.debug("SOAP request: %s", soap_action)
        try:
            async with self._session.post(
                API_ENDPOINT,
                data=envelope.encode("utf-8"),
                headers=headers,
                timeout=_REQUEST_TIMEOUT,
            ) as resp:
                if store_cookies:
                    for cookie in resp.cookies.values():
                        self._cookies[cookie.key] = cookie.value

                resp_text = await resp.text()

                if resp.status != 200:
                    _LOGGER.debug(
                        "SOAP %s HTTP %s: %s",
                        soap_action,
                        resp.status,
                        resp_text[:2000],
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("SOAP %s connection error: %s", soap_action, err)
            raise VitotrolError(f"Connection error: {err}") from err

        try:
            root = _safe_xml_fromstring(resp_text)
        except ElementTree.ParseError as err:
            raise VitotrolError(f"Invalid XML response: {err}") from err

        _strip_ns(root)

        # Find the operation result element
        result_tag = f"{soap_action}Result"
        result_el = root.find(f".//{result_tag}")
        if result_el is None:
            raise VitotrolError(
                f"Missing {result_tag} in response"
            )

        ergebnis_el = result_el.find("Ergebnis")
        if ergebnis_el is None:
            raise VitotrolError("Missing Ergebnis in response")

        result_code = int(ergebnis_el.text or "-1")
        if result_code != 0:
            error_text = _find_text_opt(result_el, "ErgebnisText") or "Unknown error"
            if soap_action == "Login":
                raise VitotrolAuthError(
                    f"Login failed: {error_text} (code {result_code})"
                )
            raise VitotrolError(
                f"{soap_action} failed: {error_text} (code {result_code})"
            )

        return result_el


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _xml_escape(text: str) -> str:
    """Escape special characters for XML content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _find_text(element: ElementTree.Element, tag: str) -> str:
    """Find a child element and return its text, raising on missing."""
    child = element.find(f".//{tag}")
    if child is None or child.text is None:
        raise VitotrolError(f"Missing <{tag}> in response")
    return child.text


def _find_text_opt(element: ElementTree.Element, tag: str) -> str | None:
    """Find a child element and return its text, or None if missing."""
    child = element.find(f".//{tag}")
    if child is None:
        return None
    return child.text
