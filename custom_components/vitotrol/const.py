"""Constants for the Viessmann Vitotrol integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "vitotrol"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# SOAP API
API_ENDPOINT = (
    "https://vitotrolapp.viessmann-climatesolutions.com"
    "/app_vitodata/VIIWebService-1.16.0.0/iPhoneWebService.asmx"
)
API_NAMESPACE = "http://www.e-controlnet.de/services/vii/"
APP_ID = "prod"
APP_VERSION = "4.3.1"
APP_OS = "Android"

# Polling defaults
DEFAULT_SCAN_INTERVAL = 300  # seconds
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 900

# Async wait parameters (from go-vitotrol)
REFRESH_INITIAL_WAIT = 8  # seconds
REFRESH_MIN_WAIT = 1
REFRESH_TIMEOUT = 60

WRITE_INITIAL_WAIT = 4
WRITE_MIN_WAIT = 1
WRITE_TIMEOUT = 60

# Config entry keys
CONF_SCAN_INTERVAL = "scan_interval"

# ---------------------------------------------------------------------------
# Attribute IDs
# ---------------------------------------------------------------------------

# Temperature sensors (RO, double)
ATTR_INDOOR_TEMP = 5367
ATTR_OUTDOOR_TEMP = 5373
ATTR_SMOKE_TEMP = 5372
ATTR_BOILER_TEMP = 5374
ATTR_HOT_WATER_TEMP = 5381
ATTR_HOT_WATER_OUT_TEMP = 5382
ATTR_HEAT_WATER_OUT_TEMP = 6052

# Temperature setpoints (RW, double)
ATTR_HEAT_NORMAL_TEMP = 82
ATTR_PARTY_MODE_TEMP = 79
ATTR_HEAT_REDUCED_TEMP = 85
ATTR_HOT_WATER_SETPOINT_TEMP = 51

# Counters (RO, double)
ATTR_BURNER_HOURS_RUN = 104
ATTR_BURNER_STARTS = 111

# Status (RO, on/off or enum)
ATTR_BURNER_STATE = 600
ATTR_INTERNAL_PUMP_STATUS = 245
ATTR_HEATING_PUMP_STATUS = 729
ATTR_CIRCULATION_PUMP_STATE = 7181

# Operating mode
ATTR_OPERATING_MODE_REQUESTED = 92  # RW, enum(0-4)
ATTR_OPERATING_MODE_CURRENT = 708  # RO, enum(0-3)

# Switches (RW, enabled)
ATTR_PARTY_MODE = 7855
ATTR_ENERGY_SAVING_MODE = 7852

# Other
ATTR_DATETIME = 5385
ATTR_CURRENT_ERROR = 7184
ATTR_HOLIDAYS_START = 306
ATTR_HOLIDAYS_END = 309
ATTR_HOLIDAYS_STATUS = 714
ATTR_WAY3_VALVE_STATUS = 5389
ATTR_FROST_PROTECTION_STATUS = 717
