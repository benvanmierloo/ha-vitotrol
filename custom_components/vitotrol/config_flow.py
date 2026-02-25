"""Config flow for the Viessmann Vitotrol integration."""

from __future__ import annotations

import asyncio
import logging
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

    def __init__(self) -> None:
        """Initialise flow state."""
        self._api: VitotrolAPI | None = None
        self._devices: list[VitotrolDevice] = []
        self._data: dict[str, Any] = {}
        self._scan_task: asyncio.Task[dict[str, list[int]]] | None = None
        self._excluded_attrs: dict[str, list[int]] = {}

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
                    self._api = api
                    self._devices = devices
                    self._data = {
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    }
                    return await self.async_step_scanning()

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Attribute scanning step — probes all attrs from GetTypeInfo
    # ------------------------------------------------------------------

    async def async_step_scanning(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show progress while probing device attributes."""
        if self._scan_task is None:
            self._scan_task = self.hass.async_create_task(
                self._async_scan_attributes_task()
            )

        if not self._scan_task.done():
            return self.async_show_progress(
                step_id="scanning",
                progress_action="scanning_attributes",
            )

        try:
            self._excluded_attrs = self._scan_task.result()
        except Exception:
            _LOGGER.exception("Attribute scan failed")
            return self.async_show_progress_done(next_step_id="scanning_failed")

        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_scanning_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle scan failure — still create the entry (no exclusions)."""
        return self.async_create_entry(
            title=self._data[CONF_USERNAME],
            data=self._data,
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the config entry after a successful scan."""
        data = {**self._data}
        if self._excluded_attrs:
            data[CONF_EXCLUDED_ATTRS] = self._excluded_attrs
        return self.async_create_entry(
            title=self._data[CONF_USERNAME],
            data=data,
        )

    # ------------------------------------------------------------------
    # Background scanning logic
    # ------------------------------------------------------------------

    async def _async_scan_attributes_task(self) -> dict[str, list[int]]:
        """Probe all device attrs in background, signal flow when done."""
        try:
            return await self._async_probe_all_devices()
        finally:
            self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)

    async def _async_probe_all_devices(self) -> dict[str, list[int]]:
        """Probe attributes for every device, return excluded map.

        Returns ``{device_id_str: [bad_attr_id, ...]}`` (only devices
        with exclusions appear).
        """
        assert self._api is not None
        excluded: dict[str, list[int]] = {}

        for device in self._devices:
            catalog = await self._api.get_type_info(device)
            readable_ids = sorted(
                aid for aid, info in catalog.items() if info.readable
            )
            if not readable_ids:
                continue

            # Optimistic: try all at once
            try:
                await self._api.get_data(device, readable_ids)
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
                bad = await self._bisect_bad_attrs(device, readable_ids)
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
        self, device: VitotrolDevice, attr_ids: list[int]
    ) -> list[int]:
        """Binary-search to isolate attr_ids that cause API errors."""
        assert self._api is not None

        if len(attr_ids) <= 1:
            try:
                await self._api.get_data(device, attr_ids)
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
                await self._api.get_data(device, half)
            except VitotrolError:
                bad.extend(await self._bisect_bad_attrs(device, half))

        return bad

    # ------------------------------------------------------------------
    # Options flow
    # ------------------------------------------------------------------

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
        """Manage scan interval."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]},
            )

        current_interval = self._config_entry.options.get(
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
