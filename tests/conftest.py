"""Shared pytest fixtures for Vitotrol integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry


# Allow the test hass instance to load our custom integration.
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return enable_custom_integrations

from custom_components.vitotrol.api import AttributeTypeInfo, VitotrolDevice
from custom_components.vitotrol.const import CONF_SCAN_INTERVAL, DOMAIN


# ---------------------------------------------------------------------------
# Minimal fake device returned by api.get_devices()
# ---------------------------------------------------------------------------

FAKE_DEVICE = VitotrolDevice(
    device_id=1001,
    device_name="Vitovalor 300-P",
    location_id=2001,
    location_name="Home",
    has_error=False,
    is_connected=True,
)

# A minimal attribute catalog entry (outdoor temperature, attr_id=5373)
FAKE_ATTR_INFO = AttributeTypeInfo(
    attr_id=5373,
    name="Temp_Aussen",
    type="Double",
    type_value=3,
    min_value=-50.0,
    max_value=70.0,
    unit="°C",
    group="Temperaturen",
    readable=True,
    writable=False,
    factory_default=None,
    heating_circuit_id=None,
    enum_values=None,
)

# Raw data that the coordinator would have after a successful refresh
FAKE_COORDINATOR_DATA = {
    FAKE_DEVICE.device_id: {
        5373: "12.5",  # outdoor temp
    }
}


# ---------------------------------------------------------------------------
# Config entry fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with test credentials."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "secret",
        },
        options={CONF_SCAN_INTERVAL: 300},
        unique_id="user@example.com",
    )


# ---------------------------------------------------------------------------
# Mock API fixture — patches VitotrolAPI for all tests that use it.
# Both patch locations share the same mock class so that
# mock_api.return_value is identical whether the API is instantiated by
# config_flow.py or __init__.py.
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_api() -> Generator[MagicMock, None, None]:
    """Patch VitotrolAPI so no real HTTP calls are made.

    The returned mock has sensible defaults:
    - login() succeeds
    - get_devices() returns [FAKE_DEVICE]
    - get_type_info() returns {5373: FAKE_ATTR_INFO}
    - refresh_data_wait() returns {5373: "12.5"}
    """
    mock_cls = MagicMock()
    instance = mock_cls.return_value
    instance.login = AsyncMock()
    instance.get_devices = AsyncMock(return_value=[FAKE_DEVICE])
    instance.get_type_info = AsyncMock(return_value={5373: FAKE_ATTR_INFO})
    instance.refresh_data_wait = AsyncMock(return_value={5373: "12.5"})
    instance.write_data_wait = AsyncMock()

    with patch(
        "custom_components.vitotrol.config_flow.VitotrolAPI",
        mock_cls,
    ), patch(
        "custom_components.vitotrol.VitotrolAPI",
        mock_cls,
    ):
        yield mock_cls
