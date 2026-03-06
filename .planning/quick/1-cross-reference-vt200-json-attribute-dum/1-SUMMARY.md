# Quick Task 1: Cross-reference VT200 JSON attribute dump — Summary

**Completed:** 2026-03-06
**Commit:** 5aa05ba

## What was done

Cross-referenced all 85 attributes from a real VT 200 (HO1C) device debug dump (`vt200.json`) against `custom_components/vitotrol/attributes.py`.

## Results

- **78 of 85** attributes were already correctly implemented (IDs, names, enum maps, types, categories)
- **7 attributes** were missing and have been added:

| ID | Name | Category | Notes |
|----|------|----------|-------|
| 7179 | Hot water charging status | `enum` | 3-value: Inactive/Charging/Afterrun |
| 7194 | Heating schedule HC2 | `none` | CircuitTime, not parseable as entity |
| 7195 | Hot water schedule HC2 | `none` | CircuitTime, not parseable as entity |
| 7196 | Circulation schedule HC2 | `none` | CircuitTime, not parseable as entity |
| 10796 | Room temp sensor 1 status | `enum` | Diagnostic, same map as 10761 |
| 10797 | Room temp sensor 2 status | `enum` | Diagnostic, same map as 10761 |
| 10800 | Room temp sensor 3 status | `enum` | Diagnostic, same map as 10761 |

## Verification

- All 85 VT200 attribute IDs now present in registry
- All enum maps verified correct (English translations match German originals)
- `_ON_VALUES[245] = ("1", "3")` confirmed correct against VT200 data
- 137 existing tests pass
- Attributes not in VT200 but in registry (e.g., 6052, heat pump attrs) are expected — different device types

## Key insight

The VT 200 (HO1C) uses the **boiler** attribute set (92, 708, 600, 5367, etc.), not the heat pump set. The existing boiler `ClimateMeta` configuration is the correct one for this device.
