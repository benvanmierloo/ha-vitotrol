"""Tests for the Vitotrol config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.vitotrol.api import VitotrolAuthError, VitotrolError
from custom_components.vitotrol.const import DOMAIN

from .conftest import FAKE_DEVICE


async def test_user_flow_success(hass: HomeAssistant, mock_api) -> None:
    """Complete setup via user step creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "user@example.com"
    assert result["data"] == {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "secret",
    }


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Second setup with same username aborts with already_configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_api) -> None:
    """Wrong credentials → invalid_auth error shown, form re-displayed."""
    mock_api.return_value.login = AsyncMock(side_effect=VitotrolAuthError("bad pass"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "wrong"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant, mock_api) -> None:
    """Network error → cannot_connect error shown, form re-displayed."""
    mock_api.return_value.login = AsyncMock(side_effect=VitotrolError("timeout"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_no_devices(hass: HomeAssistant, mock_api) -> None:
    """Login succeeds but account has no devices → no_devices error."""
    mock_api.return_value.get_devices = AsyncMock(return_value=[])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}


async def test_options_flow_sets_scan_interval(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Options flow lets the user change the scan interval."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 120}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options["scan_interval"] == 120
