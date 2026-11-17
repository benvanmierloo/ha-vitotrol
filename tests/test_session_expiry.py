"""Session-expiry behaviour against a stateful fake Vitotrol server (issue #11).

Unlike test_coordinator.py, nothing in the integration is mocked here: the real
VitotrolAPI and VitotrolCoordinator run on top of a fake aiohttp session that
behaves like the Viessmann server: Login hands out a session cookie, every
other call without a valid cookie gets the exact reply from issue #11
(Ergebnis 6, "Keine aktive/gültige Session"), and a fresh Login makes calls
work again.
"""
from __future__ import annotations

import re
from http.cookies import SimpleCookie
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant

from custom_components.vitotrol import api as api_module
from custom_components.vitotrol.api import VitotrolAPI, VitotrolError
from custom_components.vitotrol.coordinator import VitotrolCoordinator

from .conftest import FAKE_ATTR_INFO, FAKE_DEVICE

NS = "http://www.e-controlnet.de/services/vii/"
SESSION_EXPIRED_TEXT = "Keine aktive/gültige Session"


class _FakeResponse:
    def __init__(self, text: str, cookies: SimpleCookie) -> None:
        self.status = 200
        self.cookies = cookies
        self._text = text

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *exc) -> None:
        return None


class FakeVitotrolServer:
    """Minimal stateful stand-in for the Vitotrol SOAP endpoint."""

    def __init__(self) -> None:
        self.valid_sessions: set[str] = set()
        self.login_ok = True
        # When True, every non-Login call is rejected with code 6, even with
        # a fresh session (server-side trouble, not bad credentials).
        self.always_reject_session = False
        self.calls: list[str] = []
        self.writes: list[tuple[int, str]] = []
        self._next_session = 0

    def expire_sessions(self) -> None:
        self.valid_sessions.clear()

    # aiohttp.ClientSession.post() signature as used by VitotrolAPI
    def post(self, url, *, data: bytes, headers: dict, timeout) -> _FakeResponse:
        action = headers["SOAPAction"].removeprefix(NS)
        self.calls.append(action)
        body = data.decode("utf-8")
        cookies: SimpleCookie = SimpleCookie()

        if action == "Login":
            if not self.login_ok:
                return _FakeResponse(_result("Login", 1, "Benutzer oder Passwort falsch"), cookies)
            self._next_session += 1
            sid = f"session-{self._next_session}"
            self.valid_sessions.add(sid)
            cookies["ASP.NET_SessionId"] = sid
            return _FakeResponse(_result("Login", 0), cookies)

        sid = _cookie_value(headers.get("Cookie", ""), "ASP.NET_SessionId")
        if self.always_reject_session or sid not in self.valid_sessions:
            return _FakeResponse(_result(action, 6, SESSION_EXPIRED_TEXT), cookies)

        if action == "WriteData":
            attr_id = int(_tag(body, "DatapointId"))
            self.writes.append((attr_id, _tag(body, "Wert")))
            return _FakeResponse(_result(action, 0, extra="<AktualisierungsId>w1</AktualisierungsId>"), cookies)
        if action in ("RequestWriteStatus", "RequestRefreshStatus"):
            return _FakeResponse(_result(action, 0, extra="<Status>4</Status>"), cookies)
        if action == "RefreshData":
            return _FakeResponse(_result(action, 0, extra="<AktualisierungsId>r1</AktualisierungsId>"), cookies)
        if action == "GetData":
            values = (
                "<DatenwerteListe><WerteListe>"
                "<DatenpunktId>5373</DatenpunktId><Wert>12.5</Wert>"
                "</WerteListe></DatenwerteListe>"
            )
            return _FakeResponse(_result(action, 0, extra=values), cookies)
        raise AssertionError(f"Unexpected SOAP action {action}")


def _result(action: str, code: int, text: str | None = None, extra: str = "") -> str:
    err = f"<ErgebnisText>{text}</ErgebnisText>" if text else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<soap:Body><{action}Response xmlns="{NS}"><{action}Result>'
        f"<Ergebnis>{code}</Ergebnis>{err}{extra}"
        f"</{action}Result></{action}Response></soap:Body></soap:Envelope>"
    )


def _tag(body: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", body)
    assert match, f"<{tag}> missing from request"
    return match.group(1)


def _cookie_value(header: str, name: str) -> str | None:
    for part in header.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return None


@pytest.fixture(autouse=True)
def _no_poll_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_module, "WRITE_INITIAL_WAIT", 0)
    monkeypatch.setattr(api_module, "WRITE_MIN_WAIT", 0)
    monkeypatch.setattr(api_module, "REFRESH_INITIAL_WAIT", 0, )
    monkeypatch.setattr(api_module, "REFRESH_MIN_WAIT", 0, )


async def _setup(hass: HomeAssistant) -> tuple[FakeVitotrolServer, VitotrolCoordinator]:
    server = FakeVitotrolServer()
    api = VitotrolAPI("user@example.com", "secret", server)  # type: ignore[arg-type]
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    coord = VitotrolCoordinator(hass, api, [FAKE_DEVICE], scan_interval=300, config_entry=entry)
    coord._attribute_catalog[FAKE_DEVICE.device_id] = {5373: FAKE_ATTR_INFO}
    coord._entity_attr_ids[FAKE_DEVICE.device_id] = {"uid_5373": {5373}}
    await api.login()
    return server, coord


async def test_fake_server_reproduces_issue_error(hass: HomeAssistant) -> None:
    """Sanity check: an expired session gives the exact error from issue #11."""
    server, coord = await _setup(hass)
    server.expire_sessions()

    with pytest.raises(VitotrolError, match=r"WriteData failed: Keine aktive/gültige Session \(code 6\)"):
        await coord.api.write_data_wait(FAKE_DEVICE, 92, "1")


async def test_read_recovers_after_session_expiry(hass: HomeAssistant) -> None:
    """Control: reads already recover (matches the reporter's observation)."""
    server, coord = await _setup(hass)
    server.expire_sessions()

    data = await coord._async_update_data()

    assert data[FAKE_DEVICE.device_id] == {5373: "12.5"}
    assert server.calls.count("Login") == 2


async def test_write_recovers_after_session_expiry(hass: HomeAssistant) -> None:
    """Issue #11: a write after session expiry must re-login and succeed."""
    server, coord = await _setup(hass)
    server.expire_sessions()

    await coord.async_write(FAKE_DEVICE, 92, "1")

    assert server.writes == [(92, "1")]
    assert server.calls.count("Login") == 2


async def test_workaround_read_then_write_succeeds(hass: HomeAssistant) -> None:
    """The reporter's workaround (update_entity before writing) works today."""
    server, coord = await _setup(hass)
    server.expire_sessions()

    await coord._async_update_data()
    await coord.async_write(FAKE_DEVICE, 92, "1")

    assert server.writes == [(92, "1")]


async def test_write_with_revoked_credentials_raises_auth_failed(hass: HomeAssistant) -> None:
    """Expired session + rejected Login (password changed) must start reauth."""
    server, coord = await _setup(hass)
    server.expire_sessions()
    server.login_ok = False

    with pytest.raises(ConfigEntryAuthFailed):
        await coord.async_write(FAKE_DEVICE, 92, "1")
    assert server.writes == []


async def test_persistent_session_error_does_not_trigger_reauth(hass: HomeAssistant) -> None:
    """Code 6 even after a successful re-login is not a credentials problem.

    It must surface as a normal error, not ConfigEntryAuthFailed (which would
    ask the user to re-enter a password that is actually fine).
    """
    server, coord = await _setup(hass)
    server.always_reject_session = True

    with pytest.raises(VitotrolError) as exc_info:
        await coord.async_write(FAKE_DEVICE, 92, "1")
    assert not isinstance(exc_info.value, ConfigEntryAuthFailed)
    assert server.calls.count("Login") == 2  # retried exactly once
