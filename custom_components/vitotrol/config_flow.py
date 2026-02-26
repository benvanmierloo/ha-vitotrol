"""Config flow for the Viessmann Vitotrol integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VitotrolAPI, VitotrolAuthError, VitotrolDevice, VitotrolError
from .const import (
    CONF_EXCLUDED_ATTRS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

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
                    # Probe attributes inline — typically takes 1-2s
                    excluded = await self._async_probe_all_devices(
                        api, devices
                    )
                    data: dict[str, Any] = {
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    }
                    if excluded:
                        data[CONF_EXCLUDED_ATTRS] = excluded
                    return self.async_create_entry(
                        title=username, data=data
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Attribute probing logic
    # ------------------------------------------------------------------

    async def _async_probe_all_devices(
        self, api: VitotrolAPI, devices: list[VitotrolDevice]
    ) -> dict[str, list[int]]:
        """Probe attributes for every device, return excluded map.

        Returns ``{device_id_str: [bad_attr_id, ...]}`` (only devices
        with exclusions appear).
        """
        excluded: dict[str, list[int]] = {}

        for device in devices:
            catalog = await api.get_type_info(device)
            readable_ids = sorted(
                aid for aid, info in catalog.items() if info.readable
            )
            if not readable_ids:
                continue

            # Optimistic: try all at once
            try:
                await api.get_data(device, readable_ids)
                _LOGGER.debug(
                    "Device %s (%d): all %d attributes passed initial probe",
                    device.device_name,
                    device.device_id,
                    len(readable_ids),
                )
            except VitotrolError as err:
                # Something is bad — bisect to find which attrs
                _LOGGER.debug(
                    "Device %s (%d): bulk probe failed (%s), bisecting %d attrs to find bad ones",
                    device.device_name,
                    device.device_id,
                    err,
                    len(readable_ids),
                )
                bad = await self._bisect_bad_attrs(api, device, readable_ids)
                if bad:
                    bad_names = []
                    for aid in bad:
                        info = catalog.get(aid)
                        name = f"{aid}:{info.name}" if info else str(aid)
                        bad_names.append(name)
                    _LOGGER.warning(
                        "Device %s (%d): excluding %d unsupported attribute(s): %s",
                        device.device_name,
                        device.device_id,
                        len(bad),
                        ", ".join(bad_names),
                    )
                    excluded[str(device.device_id)] = bad
                else:
                    _LOGGER.debug(
                        "Device %s (%d): bisect found no individual bad attrs (transient error?)",
                        device.device_name,
                        device.device_id,
                    )

        return excluded

    async def _bisect_bad_attrs(
        self,
        api: VitotrolAPI,
        device: VitotrolDevice,
        attr_ids: list[int],
    ) -> list[int]:
        """Binary-search to isolate attr_ids that cause API errors."""
        if len(attr_ids) <= 1:
            try:
                await api.get_data(device, attr_ids)
                return []
            except VitotrolError as err:
                _LOGGER.debug(
                    "Device %s: attr %s confirmed bad: %s",
                    device.device_name,
                    attr_ids[0],
                    err,
                )
                return list(attr_ids)

        mid = len(attr_ids) // 2
        left, right = attr_ids[:mid], attr_ids[mid:]

        bad: list[int] = []
        for half in (left, right):
            try:
                await api.get_data(device, half)
            except VitotrolError:
                bad.extend(await self._bisect_bad_attrs(api, device, half))

        return bad

    # ------------------------------------------------------------------
    # Options flow
    # ------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> VitotrolOptionsFlow:
        """Return the options flow handler."""
        return VitotrolOptionsFlow()


class VitotrolOptionsFlow(OptionsFlowWithReload):
    """Handle options for Vitotrol."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage scan interval."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]},
            )

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
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
                }
            ),
        )
