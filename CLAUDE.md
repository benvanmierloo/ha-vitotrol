# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Home Assistant custom component (`custom_components/vitotrol/`) for Viessmann Vitotrol boilers. Communicates directly with the Viessmann cloud SOAP API — no MQTT broker needed. Ports the Go project [vitotrol2mqtt](https://github.com/benvanmierloo/vitotrol2mqtt) (which uses [go-vitotrol](https://github.com/maxatome/go-vitotrol)) to a native HA integration in Python.

## Architecture

Five layers, each depending only on the layer below:

1. **`api.py`** — Async SOAP client (pure Python, no HA deps). Manages cookie-based sessions via a private dict over HA's shared `aiohttp.ClientSession`. Implements the async wait pattern: fire RefreshData/WriteData, poll status, then read results.
2. **`coordinator.py`** — `DataUpdateCoordinator` that polls devices on a configurable interval (default 60s). Handles re-auth on failure. Uses `GetTypeInfo` to discover all device attributes at setup; creates entities for all of them (known = enabled, rest = disabled by default).
3. **`config_flow.py`** — UI config flow (credentials) + options flow (scan interval).
4. **`__init__.py`** — Wires API → coordinator → platform forwarding.
5. **Entity platforms** (`sensor.py`, `binary_sensor.py`, `climate.py`, `switch.py`, `number.py`) — All extend `VitotrolEntity(CoordinatorEntity)`. Write operations use optimistic state updates.

Coordinator data structure: `dict[int, dict[int, str]]` → `{device_id: {attr_id: raw_value_string}}`. Entities parse raw strings to their native types.

## Vitotrol SOAP API — Critical Constraints

- **Endpoint**: `https://vitotrolapp.viessmann-climatesolutions.com/app_vitodata/VIIWebService-1.16.0.0/iPhoneWebService.asmx`
- **Namespace**: `http://www.e-controlnet.de/services/vii/`
- **RefreshData is async and slow**: fire request → wait ~8s → poll `RequestRefreshStatus` → then `GetData`. Full cycle is 10–15s.
- **WriteData is also async**: fire → wait ~4s → poll `RequestWriteStatus`. Timeout 60s.
- **GetTypeInfo discovers all attributes**: `GetTypeInfo(AnlageId, GeraetId)` returns every datapoint the device supports in one fast call, with names, types, units, min/max, RO/RW flags, and enum values. Replaces binary-search discovery entirely.
- **Unsupported attributes crash the request**: requesting an attr the device doesn't support fails the entire SOAP call. GetTypeInfo tells us exactly which attrs are valid.
- **Session lifetime is unknown**: the original Go code re-logins every loop. Our strategy: login once, re-login + retry on any API error.
- All responses have a `<Ergebnis>` result code (0 = success) and `<ErgebnisText>` error message.

## Design Documents

Detailed specs live in `docs/`:
- `01-findings.md` — Full API documentation, all 28+ attribute IDs with types/access, SOAP request/response formats
- `02-architecture.md` — System diagram, entity mappings (which attr → which HA entity), data flow
- `03-implementation-plan.md` — Phased build plan with dependency graph
- `04-attribute-configurability.md` — GetTypeInfo-based discovery + HA enable/disable pattern for all attributes

## Key Attribute IDs

Temperatures (RO): IndoorTemp=5367, OutdoorTemp=5373, BoilerTemp=5374, HotWaterTemp=5381, SmokeTemp=5372, HeatWaterOutTemp=6052.
Setpoints (RW): HeatNormalTemp=82, HeatReducedTemp=85, PartyModeTemp=79, HotWaterSetpointTemp=51.
Modes (RW): OperatingModeRequested=92 (0=off,1=DHW,2=heat+DHW,3=cont.reduced,4=cont.normal). Modes (RO): OperatingModeCurrent=708.
Switches (RW): PartyMode=7855, EnergySavingMode=7852. Status (RO): BurnerState=600, HeatingPumpStatus=729.

All device attributes are discovered via GetTypeInfo and created as entities. Known attributes are enabled by default; all others are disabled by default and can be enabled via standard HA UI.

## Implementation Order

Files must be built in dependency order: `const.py` → `api.py` → `coordinator.py` → `entity.py` → `config_flow.py` → `__init__.py` → entity platforms (parallel) → translations/metadata (parallel).
