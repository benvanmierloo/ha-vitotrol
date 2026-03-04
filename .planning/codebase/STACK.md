# Technology Stack

**Analysis Date:** 2026-03-04

## Languages

**Primary:**
- Python 3.x - Home Assistant custom integration component

**Secondary:**
- XML - SOAP API request/response handling via ElementTree

## Runtime

**Environment:**
- Home Assistant custom component runtime (Python-based)

**Package Manager:**
- pip

## Frameworks

**Core:**
- Home Assistant Framework - Custom integration framework providing ConfigEntry, ConfigFlow, DataUpdateCoordinator, entity platforms
- Location: `custom_components/vitotrol/`

**Async/HTTP:**
- aiohttp - HTTP client for SOAP API requests
- Built-in to Home Assistant's `aiohttp.ClientSession` via `async_get_clientsession()`

**XML Processing:**
- xml.etree.ElementTree (Python stdlib) - SOAP response parsing
- defusedxml.ElementTree.fromstring - Secure XML parsing (prevents XXE attacks)

**Testing:**
- pytest via pytest-homeassistant-custom-component - Test runner and fixtures
- pytest-cov - Code coverage reporting

**Configuration:**
- voluptuous (voluptuous.Schema) - Config flow schema validation
- Home Assistant ConfigFlow API - Multi-step user authentication and options

## Key Dependencies

**Critical:**
- `defusedxml>=0.7.1` - XML parsing security (required in manifest.json)
- aiohttp - Async HTTP client for SOAP communication (Home Assistant provided)

**Testing Only:**
- `pytest-homeassistant-custom-component==0.13.316` - Home Assistant test fixtures and utilities
- `pytest-cov` - Code coverage analysis

**Development Scripts:**
- aiohttp - Async HTTP support for development utilities
- defusedxml - XML security

## Configuration

**Environment:**
- Username/password credentials configured via Home Assistant UI config flow (`custom_components/vitotrol/config_flow.py`)
- Scan interval (polling frequency) configured via Home Assistant options flow
- No environment variables required; credentials stored in Home Assistant's encrypted config storage

**Build:**
- hassfest validation (GitHub Actions workflow: `.github/workflows/hassfest.yaml`)
- HACS validation (GitHub Actions workflow: `.github/workflows/hacs.yaml`)

## Platform Requirements

**Development:**
- Python 3.x runtime
- aiohttp
- defusedxml>=0.7.1
- pytest-homeassistant-custom-component==0.13.316 (for tests)
- pytest-cov (for coverage)

**Production:**
- Home Assistant 2024.x or later (custom integration)
- Python 3.x runtime (provided by Home Assistant)
- defusedxml>=0.7.1 (required dependency)
- aiohttp (provided by Home Assistant)

## Architecture Overview

**Five-layer dependency stack** (CLAUDE.md):
1. `api.py` - Pure Python async SOAP client (no HA deps, uses only aiohttp + stdlib)
2. `coordinator.py` - Home Assistant DataUpdateCoordinator for polling
3. `config_flow.py` - Home Assistant ConfigFlow UI
4. `__init__.py` - Setup/teardown wiring
5. Entity platforms - `sensor.py`, `binary_sensor.py`, `climate.py`, `switch.py`, `number.py`, `select.py`

---

*Stack analysis: 2026-03-04*
