# Vitotrol SOAP API Reference

This documents the Viessmann Vitotrol cloud SOAP API used by this integration. The API was originally built for the Vitotrol iOS/Android app.

## Connection Details

| Property | Value |
|---|---|
| Endpoint | `https://vitotrolapp.viessmann-climatesolutions.com/app_vitodata/VIIWebService-1.16.0.0/iPhoneWebService.asmx` |
| WSDL | Same URL with `?wsdl` appended |
| Protocol | SOAP 1.1 over HTTPS |
| Namespace | `http://www.e-controlnet.de/services/vii/` |
| Auth | Cookie-based session (`Login` returns `Set-Cookie`, subsequent calls send it back) |
| App identity | `AppId=prod`, `AppVersion=4.3.1`, `Betriebssystem=Android` |

## Request/Response Format

**Request envelope:**
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

**SOAPAction header:** `http://www.e-controlnet.de/services/vii/{OperationName}`

**Response structure** (every response has a result header):
```xml
<{Operation}Response>
  <{Operation}Result>
    <Ergebnis>0</Ergebnis>          <!-- 0 = success, non-zero = error -->
    <ErgebnisText></ErgebnisText>    <!-- error description if non-zero -->
    <!-- operation-specific data -->
  </{Operation}Result>
</{Operation}Response>
```

## SOAP Operations

| Operation | Purpose | Latency |
|---|---|---|
| `Login` | Authenticate with email/password, get session cookie | ~1s |
| `GetDevices` | Discover locations and devices under the account | ~1s |
| `GetTypeInfo` | Get all datapoint definitions for a device | ~1s |
| `RefreshData` | Tell device to upload fresh values (returns a refresh ID) | ~1s |
| `RequestRefreshStatus` | Poll whether RefreshData is done (0 = pending) | ~1s |
| `GetData` | Read cached attribute values from the server | ~1s |
| `WriteData` | Write a value to the device (returns a refresh ID) | ~1s |
| `RequestWriteStatus` | Poll whether WriteData is done (0 = pending) | ~1s |
| `GetErrorHistory` | Read error history from device | ~1s |
| `GetTimesheetData` | Read heating schedule for a timesheet ID | ~1s |
| `WriteTimesheetData` | Write a heating schedule | ~1s |

## Async Wait Pattern

`RefreshData` and `WriteData` are **asynchronous**. You fire the request, get a refresh ID, then poll until complete:

```
RefreshData(device, attr_ids) → refresh_id
  sleep(8s)                                    # initial wait
  RequestRefreshStatus(refresh_id) → status
  (repeat until status != 0, timeout 60s)
GetData(device, attr_ids) → values
```

A full data refresh cycle takes **10-15 seconds**. Writes are similar but faster (initial wait 4s).

## Device Model

```
Account (Login)
 └── Location (AnlageV2)
      ├── AnlageId        (location ID)
      ├── AnlageName      (location name)
      ├── HatFehler       (has error)
      ├── IstVerbunden    (is connected)
      └── Devices (GeraetV2[])
           ├── GeraetId      (device ID)
           ├── GeraetName    (device name, e.g. "VT 200 (HO1C)")
           ├── HatFehler     (has error)
           └── IstVerbunden  (is connected)
```

Most installations have one location with one device. Device-scoped operations (`GetData`, `RefreshData`, `WriteData`) require both `AnlageId` and `GeraetId`.

## GetTypeInfo — Attribute Discovery

`GetTypeInfo(AnlageId, GeraetId)` returns **all available datapoints** for a device in one call. This is the proper way to discover supported attributes — no brute-force scanning needed.

**Response:** `TypeInfoListe` containing `DatenpunktTypInfo` entries:

| Field | Type | Description |
|---|---|---|
| `DatenpunktId` | string | Attribute ID: plain number (`"5367"`) or enum value (`"92-0"`) |
| `DatenpunktName` | string | Human-readable name (German) |
| `DatenpunktTyp` | string | Type: `"ENUM"`, `"DOUBLE"`, etc. |
| `DatenpunktTypWert` | byte | Numeric type code |
| `MinimalWert` | string | Minimum value; for enum entries (`"ID-N"`), contains the label |
| `MaximalWert` | string | Maximum value |
| `EinheitBezeichnung` | string | Unit: `"°C"`, `"kW"`, `"h"`, etc. |
| `DatenpunktGruppe` | string | Group/category |
| `HeizkreisId` | string | Heating circuit ID |
| `Auslieferungswert` | string | Factory default value |
| `IstLesbar` | bool | Readable flag |
| `IstSchreibbar` | bool | Writable flag |

**Enum handling:** Enum attributes produce multiple entries:
- Base attribute: plain ID (`"92"`), type `"ENUM"`
- Per-value entries: `"92-0"`, `"92-1"`, `"92-2"`, ... — `MinimalWert` contains the label
  - Example: `"92-0"` → `MinimalWert = "Abschaltbetrieb"` (off)

## Known Attributes

These are the well-known attribute IDs used by the integration's hardcoded entity definitions. Devices may support many more — discovered via `GetTypeInfo`.

### Temperatures (read-only)

| ID | Name | Unit |
|---|---|---|
| 5367 | Indoor temperature | °C |
| 5373 | Outdoor temperature | °C |
| 5372 | Smoke/exhaust temperature | °C |
| 5374 | Boiler temperature | °C |
| 5381 | Hot water storage temperature | °C |
| 5382 | Hot water outlet temperature | °C |
| 6052 | Heating water outlet temperature | °C |

### Setpoints (read-write)

| ID | Name | Unit |
|---|---|---|
| 82 | Normal room temperature setpoint | °C |
| 85 | Reduced room temperature setpoint | °C |
| 79 | Party mode temperature setpoint | °C |
| 51 | Hot water temperature setpoint | °C |

### Operating Modes

| ID | Name | Access | Values |
|---|---|---|---|
| 92 | Requested operating mode | RW | 0=off, 1=DHW only, 2=heat+DHW, 3=cont. reduced, 4=cont. normal |
| 708 | Current operating mode | RO | 0=stand-by, 1=reduced, 2=normal, 3=cont. normal |

### Status

| ID | Name | Access | Values |
|---|---|---|---|
| 600 | Burner state | RO | 0=off, 1=on |
| 245 | Internal pump status | RO | 0-3 enum |
| 729 | Heating pump status | RO | 0=off, 1=on |
| 7181 | Circulation pump state | RO | 0=off, 1=on |
| 717 | Frost protection status | RO | 0=inactive, 1=active |
| 5389 | 3-way valve status | RO | 0=undefined, 1=heating, 2=middle, 3=hot water |
| 7184 | Current error | RO | String |

### Switches

| ID | Name | Access |
|---|---|---|
| 7855 | Party mode | RW |
| 7852 | Energy saving mode | RW |

### Counters

| ID | Name | Access | Unit |
|---|---|---|---|
| 104 | Burner runtime | RO | hours |
| 111 | Burner starts | RW | count |

### Other

| ID | Name | Access |
|---|---|---|
| 5385 | Device date/time | RW |
| 306 | Holidays start date | RW |
| 309 | Holidays end date | RW |
| 714 | Holiday program active | RO |

## Important Constraints

1. **Unsupported attributes break the whole request.** If you include an attribute ID the device doesn't support, the entire SOAP call fails. Always use `GetTypeInfo` to discover valid attributes first.

2. **Session lifetime is unknown.** The original Go implementation re-authenticates every loop. This integration logs in once and re-authenticates on any API error.

3. **No documented rate limits.** The API was designed for a single mobile app, so avoid aggressive polling.

4. **WSDL field names are mixed German/English.** The password field is `Passwort`, the write attribute field is `DatapointId` (not `DatenpunktId`), and element order in the SOAP body should match the WSDL.

## Related Projects

- [go-vitotrol](https://github.com/maxatome/go-vitotrol) — Go SOAP client library (reference implementation)
- [vitotrol2mqtt](https://github.com/benvanmierloo/vitotrol2mqtt) — Go MQTT bridge using go-vitotrol
