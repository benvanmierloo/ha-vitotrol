# Viessmann Vitotrol for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/benvanmierloo/ha-vitotrol)](https://github.com/benvanmierloo/ha-vitotrol/issues)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-donate-yellow.svg)](https://buymeacoffee.com/benvanmierloo)

A Home Assistant custom integration for **Viessmann heating systems** that use the Vitotrol mobile app. Connects directly to the Viessmann cloud API.

## What you get

| Platform | Entities | Description |
|---|---|---|
| **Climate** | Heating | HVAC modes (Off / Auto / Heat), ECO and Boost presets, target temperature control |
| **Sensor** | 12+ sensors | Indoor, outdoor, boiler, hot water, smoke, and heating water temperatures. Burner hours, burner starts, operating mode, 3-way valve status, current error |
| **Binary sensor** | 6 sensors | Burner, internal pump, heating pump, circulation pump, frost protection, holiday mode |
| **Switch** | 2 switches | Party mode, energy saving mode |
| **Number** | 3+ controls | Hot water setpoint, reduced temperature setpoint, party mode temperature |
| **Select** | Dynamic | Writable enum attributes discovered on your device |

The integration queries your device for its full attribute catalog (`GetTypeInfo`) on first setup. Well-known attributes (listed above) are enabled by default. All other discovered attributes are created as disabled entities — enable them in the HA entity settings if you need them.

## Requirements

- A Viessmann heating system with Vitotrol connectivity
- A Viessmann account (the same credentials you use in the Vitotrol mobile app)
- Home Assistant 2024.12 or newer

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner and select **Custom repositories**
3. Add `https://github.com/benvanmierloo/ha-vitotrol` as an **Integration**
4. Search for **Viessmann Vitotrol** in HACS and install it
5. Restart Home Assistant

### Manual

1. Download the `custom_components/vitotrol` folder from this repository
2. Copy it to your Home Assistant `config/custom_components/vitotrol` directory
3. Restart Home Assistant

## Setup

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **Viessmann Vitotrol**
3. Enter your Viessmann account email and password
4. The integration will connect, discover your devices, and create entities automatically

## Configuration

After setup, click **Configure** on the integration card to adjust options:

### Scan interval

How often to poll the Viessmann API for new data (default: 300 seconds, range: 60-900 seconds).

The Vitotrol API is slow by nature — each data refresh involves telling the boiler to upload data, waiting for completion, then reading it. Lower intervals mean fresher data but more API calls.

## Climate entity

The climate entity maps Viessmann operating modes to Home Assistant:

| HA Mode | Vitotrol Mode | Description |
|---|---|---|
| **Off** | Mode 0 | System off |
| **Auto** | Mode 2 | Heating + domestic hot water (recommended) |
| **Heat** | Mode 4 | Continuous normal temperature |

### Presets

| Preset | Effect |
|---|---|
| **None** | Normal operation |
| **ECO** | Enables energy saving mode (reduced temperature) |
| **Boost** | Enables party mode (temporarily higher temperature) |

Presets are mutually exclusive — enabling ECO disables Boost and vice versa.

## Diagnostics

The integration supports Home Assistant's diagnostics feature. Go to the integration page and click **Download diagnostics** to get a JSON file with your device configuration and current data. Sensitive data (username, password) is automatically redacted.

## Troubleshooting

### "Unable to connect to the Vitotrol service"

- Verify your credentials work in the Vitotrol mobile app
- The Viessmann cloud service may be temporarily unavailable

### "No devices found under this account"

- Ensure your Viessmann device is registered and online in the Vitotrol app

### Entities show "unavailable"

- The Vitotrol API can be slow (10-15 seconds per refresh cycle). Wait for at least one full poll interval
- Check if your device is connected in the Vitotrol app
- Some attributes may not be supported by your specific boiler model — unsupported attributes are automatically excluded during discovery

### Data feels stale

The Vitotrol API uses a request-wait-poll pattern:
1. Tell the device to upload fresh data
2. Wait ~8 seconds for it to respond
3. Poll until the upload is confirmed
4. Read the data

This is inherent to the API design. The default 300-second scan interval balances freshness against API load.

## Known limitations

- **API speed**: The Viessmann cloud API is inherently slow. Data refreshes take 10-15 seconds, writes take 4-10 seconds. This cannot be improved.
- **Single session**: The integration uses one session per account. Running the Vitotrol mobile app simultaneously may cause session conflicts.
- **Cloud dependency**: All communication goes through Viessmann's cloud servers. If their service is down, the integration won't work.

## Discovery Script

A standalone script is included to explore what your device supports, without needing Home Assistant:

```
pip install -r scripts/requirements.txt
python scripts/discover.py --user YOUR_EMAIL --password YOUR_PASSWORD --values
```

This dumps every attribute your device exposes (IDs, names, types, units, min/max, read/write flags) and optionally their current values. Useful for identifying attributes to add to the integration.

## Contributing

The easiest way to contribute is adding attributes for your device. The [contributor guide](docs/contributing.md) walks through the process — it's a one-line table addition per attribute.

For deeper changes, see the [architecture overview](docs/architecture.md) and [API reference](docs/api-reference.md).

Found a bug or have a feature request? [Open an issue](https://github.com/benvanmierloo/ha-vitotrol/issues).

## License

MIT License. See [LICENSE](LICENSE) for details.

This project is not affiliated with or endorsed by Viessmann. All product names, logos, and brands are property of their respective owners.
