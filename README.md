# Viessmann Vitotrol for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/benvanmierloo/ha-vitotrol)](https://github.com/benvanmierloo/ha-vitotrol/issues)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-donate-yellow.svg)](https://buymeacoffee.com/benvanmierloo)

A Home Assistant custom integration for **Viessmann heating systems** that use the Vitotrol mobile app. Connects directly to the Viessmann cloud API — no MQTT broker, no extra hardware needed.

If you're coming from [vitotrol2mqtt](https://github.com/benvanmierloo/vitotrol2mqtt), this is the native HA replacement. Same data, better integration.

## What you get

| Platform | Entities | Description |
|---|---|---|
| **Climate** | Heating | HVAC modes (Off / Auto / Heat), ECO and Boost presets, target temperature control |
| **Sensor** | 12 sensors | Indoor, outdoor, boiler, hot water, smoke, and heating water temperatures. Burner hours, burner starts, operating mode, 3-way valve status, current error |
| **Binary sensor** | 6 sensors | Burner, internal pump, heating pump, circulation pump, frost protection, holiday mode |
| **Switch** | 2 switches | Party mode, energy saving mode |
| **Number** | 3 controls | Hot water setpoint (10-60 C), reduced temperature setpoint (3-30 C), party mode temperature (10-30 C) |

Only entities supported by your specific device are created. The integration automatically discovers which attributes your boiler supports on first setup.

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

How often to poll the Viessmann API for new data (default: 60 seconds, range: 30-600 seconds).

The Vitotrol API is slow by nature — each data refresh involves telling the boiler to upload data, waiting for completion, then reading it. Lower intervals mean fresher data but more API calls.

### Custom attributes

The integration auto-discovers ~24 known attributes. If your device has additional data points (common with newer Viessmann models), you can add them as custom sensors.

Enter one attribute per line using the format `name-0xHHHH` where `HHHH` is the hex attribute ID:

```
info_elektrische_leistung-0x2637
info_thermische_leistung-0x266c
info_energie_gesamt-0x2e68
info_waermemenge_fcu-0x2639
```

Custom attributes appear as sensor entities. The name part becomes the entity name (underscores are converted to spaces).

#### Migrating from vitotrol2mqtt

If you have a working `vitotrol2mqtt.yml` config, copy your custom field names directly into the options text area. Known fields like `IndoorTemp` and `OutdoorTemp` are handled automatically — only paste the custom `name-0xNNNN` entries.

#### Finding custom attribute IDs

Custom attribute IDs can be discovered by:
- Checking community forums for your boiler model
- Referencing the [go-vitotrol](https://github.com/maxatome/go-vitotrol) source code
- Trial and error with hex ranges common for your device type (e.g. `0x2600`-`0x2700`)

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

This is inherent to the API design. A 60-second scan interval is a good balance between freshness and API load.

## Known limitations

- **API speed**: The Viessmann cloud API is inherently slow. Data refreshes take 10-15 seconds, writes take 4-10 seconds. This cannot be improved.
- **Single session**: The integration uses one session per account. Running the Vitotrol mobile app simultaneously may cause session conflicts.
- **Cloud dependency**: All communication goes through Viessmann's cloud servers. If their service is down, the integration won't work.

## Support

Found a bug or have a feature request? [Open an issue](https://github.com/benvanmierloo/ha-vitotrol/issues).

## License

MIT License. See [LICENSE](LICENSE) for details.

This project is not affiliated with or endorsed by Viessmann. All product names, logos, and brands are property of their respective owners.
