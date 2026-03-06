# Quick Task 1: Cross-reference VT200 JSON attribute dump

**Created:** 2026-03-06
**Status:** Ready

## Analysis Summary

Cross-referenced 73 attributes from VT 200 (HO1C) debug dump against `attributes.py`.

- **66 of 73** attributes already correctly implemented (IDs, enum maps, on_values, types, categories all match)
- **7 attributes** missing from registry

## Task 1: Add missing VT200 attributes to registry

**Files:** `custom_components/vitotrol/attributes.py`
**Action:** Add 7 missing attribute rows + enum maps

### Missing attributes to add:

| ID | Name | Type | Category | Section |
|----|------|------|----------|---------|
| 7179 | Hot water charging status | ENUM (0=inactive, 1=charging, 2=afterrun) | `enum` | Enum status sensors |
| 7194 | Heating schedule HC2 | CircuitTime | `none` | HC2 section |
| 7195 | Hot water schedule HC2 | CircuitTime | `none` | HC2 section |
| 7196 | Circulation schedule HC2 | CircuitTime | `none` | HC2 section |
| 10796 | Room temp sensor 1 status | ENUM (OK/short/open/unknown/not present) | `enum` | Enum status sensors (diagnostic) |
| 10797 | Room temp sensor 2 status | ENUM | `enum` | Enum status sensors (diagnostic) |
| 10800 | Room temp sensor 3 status | ENUM | `enum` | Enum status sensors (diagnostic) |

### Enum maps to add:
- 7179: `{"0": "Inactive", "1": "Charging", "2": "Afterrun"}`
- 10796/10797/10800: same map as 10761 (OK/Short circuit/Open circuit/Unknown/Not present)

**Verify:** All 73 VT200 attribute IDs present in ATTRIBUTE_REGISTRY after change.
**Done:** `attributes.py` updated with 7 new rows + enum maps.
