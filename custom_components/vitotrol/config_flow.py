"""Config flow for the Viessmann Vitotrol integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .api import VitotrolAPI, VitotrolAuthError, VitotrolError
from .const import (
    CONF_CUSTOM_ATTRIBUTES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

_CUSTOM_ATTR_RE = re.compile(r"^(.+)-0x([0-9a-fA-F]{1,4})$")

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class VitotrolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vitotrol."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            api = VitotrolAPI(username, password, session)

            try:
                await api.login()
                devices = await api.get_devices()
            except VitotrolAuthError as err:
                _LOGGER.warning("Authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except (VitotrolError, aiohttp.ClientError) as err:
                _LOGGER.error("Failed to connect to Vitotrol: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(
                        title=username,
                        data={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> VitotrolOptionsFlow:
        """Return the options flow handler."""
        return VitotrolOptionsFlow(config_entry)


class VitotrolOptionsFlow(OptionsFlow):
    """Handle options for Vitotrol."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage scan interval and custom attributes."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Parse custom attributes
            custom_attrs: list[dict[str, Any]] = []
            raw_attrs = user_input.get(CONF_CUSTOM_ATTRIBUTES, "").strip()

            if raw_attrs:
                # Support both newlines and commas as separators
                entries = re.split(r"[,\n]+", raw_attrs)
                for line in entries:
                    line = line.strip()
                    if not line:
                        continue
                    match = _CUSTOM_ATTR_RE.match(line)
                    if not match:
                        errors[CONF_CUSTOM_ATTRIBUTES] = "invalid_custom_attr"
                        break
                    name = match.group(1)
                    attr_id = int(match.group(2), 16)
                    custom_attrs.append({"name": name, "attr_id": attr_id})

            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                        CONF_CUSTOM_ATTRIBUTES: custom_attrs,
                    },
                )

        current_options = self._config_entry.options
        current_interval = current_options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        # Rebuild the text area content from stored custom attributes
        current_custom = current_options.get(CONF_CUSTOM_ATTRIBUTES, [])
        custom_text = "\n".join(
            f"{c['name']}-0x{c['attr_id']:04X}" for c in current_custom
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): vol.All(
                        int,
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Optional(
                        CONF_CUSTOM_ATTRIBUTES, default=custom_text
                    ): TextSelector(TextSelectorConfig(multiline=True)),
                }
            ),
            errors=errors,
        )
