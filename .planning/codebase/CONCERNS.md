# Codebase Concerns

**Analysis Date:** 2026-03-04

## Tech Debt

**Fragile WriteData value conversion:**
- Issue: Converting floating-point values to integers via `str(int(float(value)))` assumes all writable attributes accept whole numbers only. This is undocumented API behavior inferred from the go-vitotrol library.
- Files: `custom_components/vitotrol/api.py:287`
- Impact: If Viessmann adds writable decimal-valued attributes in the future, writes will silently round/truncate values without user notification, causing silent data loss or incorrect heating curve parameters.
- Fix approach: Document this limitation in code comments. Add validation to `VitotrolNumber.async_set_native_value()` to explicitly check if the attribute supports decimals via GetTypeInfo metadata (`AttributeTypeInfo.min_value`/`max_value` parsing), or make this configurable per attribute in the registry.

**Optimistic state updates without failure rollback:**
- Issue: All write operations in entity platforms (climate, switch, number, select) update the coordinator's in-memory data store immediately via `_update_coordinator_data()`, before the actual WriteData operation completes.
- Files: `custom_components/vitotrol/climate.py:197,209,226-251`, `custom_components/vitotrol/switch.py:89,97`, `custom_components/vitotrol/number.py:120`, `custom_components/vitotrol/select.py:105`
- Impact: If WriteData fails (network error, API timeout, invalid value), the entity will display the optimistic value indefinitely until the next coordinator refresh (default 300s). Users see the wrong state and may retry commands thinking they failed. In multi-device scenarios with concurrent writes, this can cause UI inconsistency.
- Fix approach: Wrap coordinator mutations in try-except blocks. On WriteData failure, revert the optimistic update by querying the current value from `_device_data` and resetting the entity state. Consider storing a "pending write" marker to avoid confusion during the async wait window.

**Attribute catalog generation at setup cannot be recovered:**
- Issue: `GetTypeInfo` is called once during `async_setup_entry()` in `__init__.py:60`. If it fails, the integration raises `ConfigEntryNotReady`, blocking startup. If credentials are correct but the API returns an empty catalog (edge case), no error is raised, but entity discovery silently produces no entities.
- Files: `custom_components/vitotrol/__init__.py:59-64`, `custom_components/vitotrol/coordinator.py:92-106`
- Impact: A transient GetTypeInfo failure (API hiccup, network glitch) blocks HA startup even though future polls might succeed. An empty catalog is not flagged as an error, so a user won't know why they see no entities.
- Fix approach: Log a warning if GetTypeInfo returns fewer attributes than a minimum threshold (e.g., 5 core attributes like temperature sensors). Allow setup to proceed with a degraded catalog but emit diagnostic warnings. On subsequent polls, retry GetTypeInfo if it hasn't been called yet.

**No mutex protecting concurrent writes to coordinator.data:**
- Issue: Multiple entity write operations can happen in parallel. Each calls `async_write()` which eventually calls `_update_coordinator_data()` to mutate the shared dictionary. There is no lock protecting these mutations.
- Files: `custom_components/vitotrol/entity.py:216-227`, accessed from all entity platforms
- Impact: In rare cases with many simultaneous user actions (e.g., climate preset + number + switch all clicked in rapid succession), concurrent dict mutations could corrupt the in-memory state, causing entities to read stale or invalid values. This is unlikely due to HA's event loop being single-threaded at the Python level, but the code assumes this without documentation.
- Fix approach: Add inline comment in `entity.py:_update_coordinator_data()` documenting that mutations are safe only within the async event loop. If coordinator is ever accessed from non-async contexts in the future, add thread-safe access (RLock or asyncio.Lock).

## Known Bugs

**Climate preset mutual exclusion incomplete:**
- Symptoms: If both eco_mode and party_mode attributes are present but one is writable and the other is read-only, the preset switching logic breaks.
- Files: `custom_components/vitotrol/climate.py:212-253`
- Trigger: Set a preset on a device with mismatched RO/RW eco/party attributes, then read the logs.
- Current behavior: The code blindly writes to `eco_attr` and `party_attr` if they are not None, assuming both are writable. If one is RO, `coordinator.async_write()` will call the API with a read-only attribute, which will fail silently (WriteData returns an error, caught in coordinator, logged, but entity state was already updated optimistically).

**Inferred metadata for binary enum detection may fail silently:**
- Symptoms: Unknown binary_sensor with German enum labels not mapping correctly to on/off.
- Files: `custom_components/vitotrol/binary_sensor.py:70-76`
- Trigger: Device with custom enum like `{"0": "Aus", "1": "Betrieb"}` (instead of "Aus"/"Ein").
- Current behavior: The code looks for labels matching `("ein", "aktiv")` in lowercase. If the device uses `"Betrieb"`, no on_keys are found, and `self._on_values` defaults to `("1",)`, which may not be correct.

**Number entity step size hardcoded to 1.0:**
- Symptoms: Number entities don't respect min/max bounds on fractional inputs even if the attribute supports decimals.
- Files: `custom_components/vitotrol/number.py:90`
- Trigger: Manually set a number attribute to 20.5 (if it supports decimals) via the HA UI.
- Current behavior: The step is fixed at `1.0`, so the UI slider will only show integer increments. The actual write will still convert `20.5` to `20` via `int(value)`.

## Security Considerations

**Credentials stored in plaintext in config entry data:**
- Risk: The username and password are stored unencrypted in HA's config entry storage.
- Files: `custom_components/vitotrol/config_flow.py:74-79`, `custom_components/vitotrol/__init__.py:44-45`
- Current mitigation: Home Assistant stores config entries in a database that is typically on the same disk as HA config. If the HA machine is physically compromised or a backup is stolen, credentials are exposed. Diagnostics redact the password but the data dict still contains it in memory.
- Recommendations: This is standard HA practice (most integrations store API tokens in plaintext), but users should be aware that a compromised HA instance = compromised Viessmann account. Document this in CONTRIBUTING.md. Consider adding a note in the setup flow warning about credential security.

**Cookie-based session management lacks timeout enforcement:**
- Risk: The API stores session cookies in `VitotrolAPI._cookies` (a dict). No expiration tracking or timeout is implemented.
- Files: `custom_components/vitotrol/api.py:108,395-410`
- Current mitigation: The go-vitotrol library (original source) re-logs in every loop. This integration re-logs on any API error (auth or otherwise), so stale cookies are eventually invalidated. However, if the API silently stops accepting a cookie without returning a 401, the integration won't know to re-login until the next error.
- Recommendations: Add a `last_login_time` timestamp to `VitotrolAPI`. Force re-login if no refresh has happened in >24 hours, even if no errors occurred. This prevents indefinite session reuse.

**XML injection not fully mitigated:**
- Risk: User-controlled data (username, password, refresh_id, attribute values) is XML-escaped before insertion into SOAP bodies. However, the escape function is custom-written.
- Files: `custom_components/vitotrol/api.py:463-471`, called at lines 118, 119, 261, 293, etc.
- Current mitigation: The `_xml_escape()` function escapes the five critical XML entities: `&`, `<`, `>`, `"`, `'`. This is correct for text content.
- Recommendations: The code is safe, but using `xml.etree.ElementTree` to build SOAP bodies (rather than string concatenation) would be more robust. This is a nice-to-have refactor, not a blocking issue.

## Performance Bottlenecks

**GetTypeInfo discovery is O(catalog_size) in memory:**
- Problem: The full attribute catalog is kept in memory in `VitotrolCoordinator._attribute_catalog`. For devices with 500+ attributes, this is negligible, but large catalogs (unknown upper bound) could accumulate.
- Files: `custom_components/vitotrol/coordinator.py:82,98-99`
- Cause: The catalog is loaded once at setup and never pruned. If a device is updated to support new attributes, the old catalog is discarded when the integration is reloaded.
- Improvement path: This is a low priority issue. If needed, implement LRU eviction or lazy loading of the catalog from a persistent file.

**Polling all registered entities even if some are unused:**
- Problem: `_get_attr_ids()` returns the union of all attr_ids from all registered entities. If 100 entities are registered but only 10 are enabled, all 100 attrs are polled every refresh cycle.
- Files: `custom_components/vitotrol/coordinator.py:197-218`
- Cause: The coordinator doesn't track entity `enabled` state — it only sees registrations. Disabled entities remain registered and consume API bandwidth.
- Improvement path: Add a callback to the coordinator when an entity's `enabled` state changes in HA. Unregister disabled entities' attr_ids from the poll set. This requires integration with HA's entity registry, which is more complex.

**Climate entity mutates multiple attributes sequentially in async_set_preset_mode:**
- Problem: Setting a preset may require 2-3 async API calls: disable party mode, enable eco mode, etc. Each call is awaited sequentially.
- Files: `custom_components/vitotrol/climate.py:212-253`
- Cause: The logic is correct (mutual exclusion requires disabling one before enabling the other), but blocking calls could add 4-6 seconds of delay if the API is slow.
- Improvement path: Batch writes are not supported by the API. This is a limitation of the Viessmann SOAP interface, not the integration. Document this in README.

## Fragile Areas

**Entity registry pre-seeding logic assumes stable entity UIDs:**
- Files: `custom_components/vitotrol/coordinator.py:112-177`
- Why fragile: The `pre_seed_from_registry()` function rebuilds a mapping of entity unique_ids to attr_ids by iterating through the attribute catalog and calling `entity_key_for_attr()` on every one. If the key generation logic changes, the mapping breaks and pre-seeding silently fails (no error, just zero entities pre-seeded).
- Safe modification: When changing `entity_key_for_attr()` logic in `entity.py:29-37`, add a corresponding unit test in `tests/test_entity_helpers.py` that verifies the key format. Before deploying, check if the change breaks existing entity unique_ids by comparing against a sample from the entity registry. If a breaking change is needed, migration logic should re-register entities with new UIDs.
- Test coverage: `tests/test_entity_helpers.py` tests the key generation. `tests/test_init.py` tests pre-seeding. Good coverage.

**Attribute metadata inference for unknown attrs relies on German name parsing:**
- Files: `custom_components/vitotrol/entity.py:72-142`, specifically `_infer_numeric_meta()` and `_group_prefix()`
- Why fragile: The inference heuristics match German attribute names (e.g., `"Anzahl_Brennerstunden"`, `"Info_Brenner_Modulation"`). If an attribute name changes language or format in a future API version, inference silently produces incorrect unit/device_class assignments.
- Safe modification: Add a comment documenting the German naming assumption. If the API ever switches language, add a language-detection layer or allow overrides in the registry. The fallback (parse as-is with no device_class) is reasonable, so silently wrong inference is unlikely to cause harm, but should be documented.
- Test coverage: `tests/test_entity_helpers.py` tests inference. Good coverage.

**Climate entity hard-codes preset list at init time:**
- Files: `custom_components/vitotrol/climate.py:95-101`
- Why fragile: The available presets are determined once in `__init__()` by checking if eco_mode and party_mode attrs exist in the catalog. If a device gains a new mode attribute after setup (e.g., via firmware update), the climate entity won't expose it until reload.
- Safe modification: Add a property `supported_preset_modes` that checks the current catalog dynamically, or re-run the preset detection on every attribute refresh. This is a minor issue (firmware updates are rare).
- Test coverage: `tests/test_climate.py` tests preset availability. Good.

**Select entity option list is immutable:**
- Files: `custom_components/vitotrol/select.py:74-81`
- Why fragile: The `_attr_options` list is built once from the enum_values dict. If the server's enum values change (e.g., firmware update adds new modes), the entity won't see new options until reload.
- Safe modification: Same as climate — add a property or refresh on each poll. Low priority.
- Test coverage: `tests/test_select.py` tests options. Good.

## Scaling Limits

**Single session per account — concurrent login conflicts:**
- Current capacity: One integration instance = one session. Running the Vitotrol mobile app on a phone while HA is active will cause session conflicts.
- Limit: If a second HA instance or the mobile app logs in, the first session's cookies become invalid, causing `VitotrolAuthError`. The integration will re-login immediately, evicting the second login.
- Scaling path: The Viessmann API doesn't support multiple concurrent sessions per account. This is an API limitation, not an integration bug. Document in README (done). Users should not run Vitotrol app while HA is active.

**GetTypeInfo fails for devices with 1000+ attributes:**
- Current capacity: Tested with real devices having ~200 attributes. Unknown upper bound.
- Limit: The SOAP response size grows with catalog size. If a future device has thousands of attributes, parsing could be slow or hit memory limits.
- Scaling path: Implement streaming/paginated GetTypeInfo if Viessmann adds it. For now, assume devices have <1000 attrs. No action needed.

## Dependencies at Risk

**Custom XML parsing via defusedxml — potential compatibility issue:**
- Risk: The code uses `defusedxml.ElementTree.fromstring()` instead of the standard library `ElementTree`. This is a security best practice (prevents XXE attacks), but defusedxml is an external dependency.
- Files: `custom_components/vitotrol/api.py:17,426`
- Impact: If defusedxml is unmaintained or incompatible with a future Python version, parsing could break. Home Assistant bundles defusedxml, so risk is low.
- Migration plan: If defusedxml is deprecated, switch to the standard library's `ElementTree.XMLParser(resolve_entities=False)` which provides XXE protection natively.

**Dependency on go-vitotrol for API constants:**
- Risk: Status code semantics (`0`=pending, `1,3`=progress, `4,9`=success) are inferred from the go-vitotrol library. These are undocumented assumptions.
- Files: `custom_components/vitotrol/api.py:347-359`
- Impact: If Viessmann changes status codes (unlikely but possible), WriteData/RefreshData polling will misinterpret responses.
- Migration plan: Document the status code mapping in a comment with a link to go-vitotrol. If polling starts failing for unknown statuses, add logging to surface the actual status code, then update the mapping.

## Missing Critical Features

**No refresh-on-demand endpoint for users:**
- Problem: Users cannot manually request an immediate data refresh. They must wait for the next scheduled poll interval (default 300s). For time-sensitive operations (checking burner status, confirming a write), this is slow.
- Blocks: Advanced users cannot perform ad-hoc queries without HA reload/restart.
- Priority: Low. The API is already slow (10-15s per refresh), so manual refresh would still feel slow. Not a blocker.

**No attribute value history or trend analysis:**
- Problem: The integration only exposes the current value. No history or min/max/average over time.
- Blocks: Users cannot see how a temperature has changed over the past hour or spot anomalies.
- Priority: Low. This is outside the scope of a basic integration. Can be implemented by users via HA's history stats or external dashboards.

**No entity grouping by heating circuit:**
- Problem: Devices with HC1/HC2/HC3 get separate entities for each circuit, but there's no UI grouping to keep them organized.
- Blocks: Large setups with 3+ circuits + 30 entities per circuit become hard to navigate.
- Priority: Low. This is a HA UI feature, not an integration limitation. Users can use entity aliases or custom dashboards.

## Test Coverage Gaps

**Untested: GetTypeInfo response with malformed enum values:**
- What's not tested: If GetTypeInfo returns an enum entry with a missing label or invalid DatenpunktId format.
- Files: `custom_components/vitotrol/api.py:167-202`, `custom_components/vitotrol/coordinator.py:92-106`
- Risk: Malformed enum values could crash entity initialization or cause silent data loss.
- Priority: Medium. Add a unit test in `tests/test_coordinator.py` with a mock GetTypeInfo response containing edge cases: empty enum_values, missing MinimalWert, null labels.

**Untested: Concurrent write_data_wait operations with errors:**
- What's not tested: Two entities calling `coordinator.async_write()` simultaneously. If one fails mid-operation, does the other still complete?
- Files: `custom_components/vitotrol/coordinator.py:222-234`, `custom_components/vitotrol/api.py:320-332`
- Risk: A failed write in entity A could interfere with an in-flight write in entity B due to the API's slow async polling.
- Priority: Medium. Add integration test with mocked slow API and two concurrent writes. Verify both complete independently.

**Untested: Optimistic state rollback on WriteData timeout:**
- What's not tested: If WriteData times out after the optimistic state update but before the write completes, does the entity revert?
- Files: `custom_components/vitotrol/api.py:375-378`, `custom_components/vitotrol/entity.py:216-227`
- Risk: Entity displays wrong state indefinitely.
- Priority: High. Add test in `tests/test_number.py` (or new `test_optimistic_updates.py`) mocking a slow WriteData that times out. Verify the entity eventually resets to the coordinator's actual value on the next refresh.

**Untested: Empty device list from GetDevices:**
- What's not tested: What happens if GetDevices returns a valid response with zero devices?
- Files: `custom_components/vitotrol/api.py:149-150`
- Risk: The code raises `VitotrolError("No devices found under account")`. This is correct, but downstream integration code doesn't test for it.
- Priority: Low. Add a test in `tests/test_config_flow.py` verifying the config flow handles this error gracefully.

**Untested: Metadata inference for numeric attributes with no name match:**
- What's not tested: A completely unknown numeric attr name that doesn't start with "temp_", "info_", etc. Does inference still assign a sensible unit?
- Files: `custom_components/vitotrol/entity.py:72-103`
- Risk: Unknown numeric attrs get platform="sensor" with no unit, which is correct, but precision inference may be wrong.
- Priority: Low. The fallback behavior is acceptable. If precision matters, users can see the raw value and adjust via HA's UI.

---

*Concerns audit: 2026-03-04*
