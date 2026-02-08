# Findings & Requirements

## Source Project Analysis: vitotrol2mqtt

The existing Go project (`benvanmierloo/vitotrol2mqtt`) bridges Viessmann Vitotrol
boiler data to MQTT. It uses the [`go-vitotrol`](https://github.com/maxatome/go-vitotrol)
library by maxatome.

### Viessmann Vitotrol SOAP API

The API is a SOAP/XML web service originally built for the Vitotrol iOS/Android app.

- **Endpoint**: `https://vitotrolapp.viessmann-climatesolutions.com/app_vitodata/VIIWebService-1.16.0.0/iPhoneWebService.asmx`
- **WSDL**: `https://vitotrolapp.viessmann-climatesolutions.com/app_vitodata/VIIWebService-1.16.0.0/iPhoneWebService.asmx?wsdl`
- **Protocol**: SOAP 1.1 over HTTPS
- **Namespace**: `http://www.e-controlnet.de/services/vii/`
- **Auth**: Cookie-based session (login returns Set-Cookie, subsequent calls send it back)
- **App identity**: AppId=`prod`, AppVersion=`4.3.1`, Betriebssystem=`Android`

### SOAP Operations

| Operation | Purpose | Latency |
|---|---|---|
| `Login` | Authenticate with email/password, get session cookie | Fast (~1s) |
| `GetDevices` | Discover locations and devices under the account | Fast (~1s) |
| `RefreshData` | Tell device to upload fresh values to server. Returns a refresh ID | Fast (~1s) |
| `RequestRefreshStatus` | Poll whether RefreshData is done (status 0 = pending) | Fast (~1s) |
| `GetData` | Read cached attribute values from the server | Fast (~1s) |
| `WriteData` | Write a value to the device. Returns a refresh ID | Fast (~1s) |
| `RequestWriteStatus` | Poll whether WriteData is done (status 0 = pending) | Fast (~1s) |
| `GetErrorHistory` | Read error history from device | Fast (~1s) |
| `GetTimesheetData` | Read heating schedule for a timesheet ID | Fast (~1s) |
| `WriteTimesheetData` | Write a heating schedule | Fast (~1s) |

**Key pattern**: RefreshData and WriteData are *asynchronous*. You fire the request,
get a refresh ID, then poll `RequestRefreshStatus`/`RequestWriteStatus` until complete.

The go-vitotrol library uses these wait parameters:
- **RefreshData**: initial wait 8s, min wait 1s, timeout 60s
- **WriteData**: initial wait 4s, min wait 1s, timeout 60s

So a full data refresh cycle takes ~10-15 seconds.

### SOAP Request/Response Format

**Request envelope**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns="http://www.e-controlnet.de/services/vii/">
<soap:Body>
  <!-- operation-specific XML here -->
</soap:Body>
</soap:Envelope>
```

**SOAPAction header**: `http://www.e-controlnet.de/services/vii/{OperationName}`

**Response structure** (every response has a ResultHeader):
```xml
<{Operation}Response>
  <{Operation}Result>
    <Ergebnis>0</Ergebnis>          <!-- 0 = success, non-zero = error -->
    <ErgebnisText></ErgebnisText>    <!-- error description -->
    <!-- operation-specific data -->
  </{Operation}Result>
</{Operation}Response>
```

### Device Model

```
Account (Login)
 └── Location (AnlageV2)
      ├── AnlageId (location ID)
      ├── AnlageName (location name)
      ├── HatFehler (has error)
      ├── IstVerbunden (is connected)
      └── Devices (GeraetV2[])
           ├── GeraetId (device ID)
           ├── GeraetName (device name, e.g. "VT 200 (HO1C)")
           ├── HatFehler (has error)
           └── IstVerbunden (is connected)
```

Most installations have 1 location with 1 device.

### Device-Scoped Operations

`GetData`, `RefreshData`, `WriteData` are scoped to a specific device using:
```xml
<GeraetId>{device_id}</GeraetId>
<AnlageId>{location_id}</AnlageId>
```

### Attribute System

Attributes are identified by numeric IDs (DatenpunktId). Each has a type, access
level, and human-readable name.

#### Known Attributes

| ID | Name | Type | Access | Description |
|---|---|---|---|---|
| 5367 | IndoorTemp | double | RO | Indoor temperature (°C) |
| 5373 | OutdoorTemp | double | RO | Outdoor temperature (°C) |
| 5372 | SmokeTemp | double | RO | Smoke/exhaust temperature (°C) |
| 5374 | BoilerTemp | double | RO | Boiler temperature (°C) |
| 5381 | HotWaterTemp | double | RO | Hot water storage temperature (°C) |
| 5382 | HotWaterOutTemp | double | RO | Hot water outlet temperature (°C) |
| 6052 | HeatWaterOutTemp | double | RO | Heating water outlet temperature (°C) |
| 82 | HeatNormalTemp | double | RW | Normal room temperature setpoint (°C) |
| 79 | PartyModeTemp | double | RW | Party mode temperature setpoint (°C) |
| 85 | HeatReducedTemp | double | RW | Reduced room temperature setpoint (°C) |
| 51 | HotWaterSetpointTemp | double | RW | Hot water temperature setpoint (°C) |
| 104 | BurnerHoursRun | double | RO | Total burner runtime (hours) |
| 106 | BurnerHoursRunReset | double | WO | Reset burner hours counter |
| 600 | BurnerState | on/off | RO | Burner on/off status |
| 111 | BurnerStarts | double | RW | Total burner start count |
| 245 | InternalPumpStatus | enum(0-3) | RO | Internal pump (off/on/off2/on2) |
| 729 | HeatingPumpStatus | on/off | RO | Heating circuit pump on/off |
| 7181 | CirculationPumpState | on/off | RO | Circulation pump on/off |
| 7855 | PartyMode | enabled | RW | Party mode on/off |
| 7852 | EnergySavingMode | enabled | RW | Energy saving mode on/off |
| 5385 | DateTime | date | RW | Device date/time |
| 7184 | CurrentError | string | RO | Current error code |
| 306 | HolidaysStart | date | RW | Holiday start date |
| 309 | HolidaysEnd | date | RW | Holiday end date |
| 714 | HolidaysStatus | enabled | RO | Holiday program active |
| 5389 | Way3ValveStatus | enum(0-3) | RO | 3-way valve (undefined/heating/middle/hot water) |
| 92 | OperatingModeRequested | enum(0-4) | RW | Requested mode (off/DHW/heat+DHW/cont.reduced/cont.normal) |
| 708 | OperatingModeCurrent | enum(0-3) | RO | Current mode (stand-by/reduced/normal/cont.normal) |
| 717 | FrostProtectionStatus | enabled | RO | Frost protection active |

#### Value Types

- **double**: Float value as string, e.g. `"21.5"` → 21.5
- **on/off enum**: `"0"` = off, `"1"` = on
- **enabled enum**: `"0"` = disabled, `"1"` = enabled
- **enum(0-N)**: Numeric string mapping to named values
- **string**: Plain text
- **date**: Date/time string

#### Custom Attributes

The Go project supports custom attributes using the pattern `NAME_0xNNNN` where
NNNN is the hex attribute ID. This allows users to access device-specific attributes
not in the official list.

### Computed Attributes (from Go project)

The Go project defines one computed attribute:

**ComputedSetpointTemp**: The effective heating setpoint, computed as:
1. If EnergySavingMode is on → HeatReducedTemp
2. If PartyMode is on → PartyModeTemp
3. Based on OperatingModeCurrent:
   - 0 (stand-by) → 0°C
   - 1 (reduced) → HeatReducedTemp
   - 2+ (normal/continuous) → HeatNormalTemp

### Important Constraints

1. **Unsupported attributes cause errors**: Requesting attributes not supported by a
   specific device model causes the API to return an error for the entire request.
   The Go README warns: "Including field mappings that are unsupported by your
   Viessmann device will cause execution to crash and exit."

2. **Session lifetime unknown**: The Go code re-authenticates on every polling loop,
   suggesting sessions may expire quickly. We need re-auth handling.

3. **Slow refresh cycle**: A full RefreshData+poll+GetData cycle takes 10-15 seconds.
   The default polling interval is 60 seconds.

4. **Rate limiting unknown**: No documented rate limits, but the API is designed for
   a single mobile app, so aggressive polling should be avoided.

5. **Write operations are slow**: WriteData+poll takes 4-10 seconds before the value
   is confirmed written to the device.

### Sample Configuration (from vitotrol2mqtt.yml)

```yaml
vitotrol:
  login: VITOTROL_USER
  password: VITOTROL_PASSWORD
  retry_timeout: 30
  frequency: 60          # polling interval in seconds

devices:
  - name: '*'            # match all devices
    location: '*'        # match all locations
    fields:
      - IndoorTemp
      - OutdoorTemp
      - BoilerTemp
      - HotWaterTemp
      - HotWaterOutTemp
      - HeatWaterOutTemp
      - HeatNormalTemp
      - PartyModeTemp
      - HeatReducedTemp
      - SmokeTemp
      - ComputedSetpointTemp
      - BurnerHoursRun
      - BurnerStarts
      - BurnerState
      - InternalPumpStatus
      - HeatingPumpStatus
      - PartyMode
      - EnergySavingMode
      - OperatingModeCurrent
      - Way3ValveStatus
```
