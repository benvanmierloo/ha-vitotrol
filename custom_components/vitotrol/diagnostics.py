"""Diagnostics support for the Viessmann Vitotrol integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import VitotrolConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VitotrolConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator

    devices_info = [
        {
            "device_id": d.device_id,
            "device_name": d.device_name,
            "location_id": d.location_id,
            "location_name": d.location_name,
            "has_error": d.has_error,
            "is_connected": d.is_connected,
        }
        for d in coordinator.devices
    ]

    # Convert int keys to strings for JSON serialization
    coord_data: dict[str, dict[str, str]] = {}
    if coordinator.data:
        for device_id, attrs in coordinator.data.items():
            coord_data[str(device_id)] = {
                str(attr_id): value for attr_id, value in attrs.items()
            }

    return {
        "config_entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "config_entry_options": dict(entry.options),
        "devices": devices_info,
        "coordinator_data": coord_data,
    }
