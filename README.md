# Bad Deed Validator

**Paranoid Engineering for OCR Deed Validation** | A rigorous system for validating financial documents in production environments.

## Overview

The Bad Deed Validator is an engineering solution that demonstrates how to build robust validation systems for mission-critical financial data. Instead of trusting LLM hallucinations, this system uses **code-based logic** to catch fraudulent or corrupted deed documents before they're recorded on the blockchain.

### The Problem
At financial institutions like Propy, if an LLM hallucinates a number on a deed (e.g., changing $1.25M to $50M), that fraudulent transaction could be recorded on the blockchain permanently. This system implements "paranoid engineering" to prevent exactly that.

### The Solution
A three-layer validation architecture:

1. **Regex-based Parsing** - Extract data without LLM hallucination risk
2. **Fuzzy Matching** - Handle county abbreviations intelligently ("S. Clara" → "Santa Clara")
3. **Code-based Sanity Checks** - Catch logical impossibilities and amount discrepancies

## Key Features

### ✅ Critical Sanity Checks

**Date Logic Validation**
- Ensures "Date Recorded" ≥ "Date Signed"
- Rejects: Documents recorded before they were signed (fraud indicator)
- Impact: Catches temporal impossibilities that might slip past ML models

**Amount Reconciliation**
- Validates numeric ($1,250,000.00) matches written form ("One Million Two Hundred Thousand Dollars")
- Detects: $50k discrepancies between formats
- Impact: Catches OCR errors and deliberate amount manipulation

### 🔍 County Matching

- **Abbreviation Handling**: "S. Clara" → "Santa Clara"
- **Fuzzy Matching**: Handles OCR variations
- **Confidence Scoring**: Low-confidence matches trigger warnings
- **Tax Rate Enrichment**: Automatically populates tax rates from reference database

### 🛡️ Error Reporting

- **Hard Errors**: Document rejection with clear reasons
- **Warnings**: Manual verification recommended (low confidence)
- **Structured Output**: JSON-compatible deed data for downstream processing

## Architecture

### Module: `validator.py`

**DeedParser** - Regex-based extraction
```python
- Extracts doc ID, county, state, dates, parties, amounts
- No LLM dependencies
- Handles OCR artifacts via regex flexibility
```

**CountyMatcher** - Intelligent county resolution
```python
- Exact matching
- Abbreviation expansion (S. Clara → Santa Clara)
- Fuzzy matching via difflib.SequenceMatcher
- Tax rate database lookup
```

**DeedValidator** - Paranoid sanity checks
```python
- Date logic validation (recorded ≥ signed)
- Amount reconciliation (numeric vs written)
- Completeness checking
- County enrichment
```

**BadDeedValidator** - Orchestrator
```python
- Coordinates parsing → validation → reporting
- Single-pass processing
- JSON-serializable output
```

### Data Files

**counties.json** - Reference database
```json
[
  {"name": "Santa Clara", "tax_rate": 0.012},
  {"name": "San Mateo", "tax_rate": 0.011},
  {"name": "Santa Cruz", "tax_rate": 0.010}
]
```

## Usage

```python
from validator import BadDeedValidator

# Initialize
validator = BadDeedValidator('counties.json')

# Process deed
raw_ocr_text = '''*** RECORDING REQ ***
Doc: DEED-TRUST-0042
County: S. Clara | State: CA
Date Signed: 2024-01-15
Date Recorded: 2024-01-10
Grantor: T.E.S.L.A. Holdings LLC
Grantee: John & Sarah Connor
Amount: $1,250,000.00 (One Million Two Hundred Thousand Dollars)
APN: 992-001-XA
Status: PRELIMINARY
*** END ***'''

report = validator.process_and_report(raw_ocr_text)

if report['status'] == 'REJECTED':
    print(f"Errors: {report['validation_summary']['errors']}")
else:
    print(f"Deed approved. Tax rate: {report['deed']['tax_rate']}")
```

## Validation Examples

### ✅ Valid Deed
```json
{
  "status": "APPROVED",
  "deed": {
    "doc_id": "DEED-TRUST-0042",
    "county_normalized": "Santa Clara",
    "date_signed": "2024-01-15",
    "date_recorded": "2024-01-15",
    "amount_numeric": 1250000.0,
    "tax_rate": 0.012
  },
  "validation_summary": {
    "errors": [],
    "warnings": ["Low confidence county match: 74%"]
  }
}
```

### ❌ Rejected: Date Logic Error
```json
{
  "status": "REJECTED",
  "validation_summary": {
    "errors": [
      "CRITICAL: Date Logic Violation - Recorded 2024-01-10 "
      "cannot be before Signed 2024-01-15. "
      "This indicates fraudulent or corrupted data."
    ]
  }
}
```

### ❌ Rejected: Amount Mismatch
```json
{
  "status": "REJECTED",
  "validation_summary": {
    "errors": [
      "CRITICAL: Amount Mismatch - Numeric ($1,250,000.00) "
      "vs Written (One Million Two Hundred Thousand Dollars). "
      "Discrepancy: $50,000.00 (4.00%). "
      "This may indicate OCR errors or fraudulent modification."
    ]
  }
}
```

## Engineering Principles

### "Paranoid Engineering" Approach

1. **Trust Code, Verify Everything**
   - Regex patterns are explicit and reviewable
   - Logic errors are code bugs, not ML uncertainty
   - Easier to audit and test

2. **Detect Logical Impossibilities**
   - Date logic: Recorded before Signed = 0% probability in real world
   - Amount discrepancy: $50k difference = clear signal
   - These checks are deterministic, not probabilistic

3. **Separate Concerns**
   - Parsing ≠ Validation ≠ Enrichment
   - Each layer can be tested independently
   - Errors are traced to specific validation stage

4. **Fail Safely**
   - Incomplete data triggers warnings, not rejection
   - Low-confidence matches get flagged for manual review
   - Status quo is rejection; approval requires passing all checks

## Design Decisions

### Why No LLM?

**Pros of LLM-based approach:**
- Flexible natural language understanding

**Cons of LLM-based approach:**
- Hallucination risks (chief concern for financial data)
- Non-deterministic (same input → different output)
- Audit trail is unclear
- Performance variable based on LLM version

**Decision:** Regex + code is deterministic, reviewable, and production-safe for well-structured OCR output.

### Why Fuzzy Matching?

County names have variations due to:
- OCR errors ("Santa" → "Sante")
- Abbreviations ("S. Clara" in input, "Santa Clara" in database)
- User entry variations

Fuzzy matching (difflib.SequenceMatcher) provides:
- Confidence scores for audit trails
- Warnings when confidence < 90%
- Deterministic results

## Testing

```bash
python -m pytest tests/
```

**Test Coverage:**
- Date logic validation (recorded before signed)
- Amount reconciliation ($50k discrepancy test case)
- County matching (abbreviation expansion, fuzzy match)
- Complete deed extraction (all fields)
- Error formatting and reporting
- 
## Interactive Testing (Google Colab)

**Run the test suite interactively in Google Colab:**

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1cENowtc7xpLmNiyKscT6yKXCfNMVsMXc)

## Files

- `validator.py` - Core validation engine (~260 lines)
- `counties.json` - County reference data
- `requirements.txt` - Dependencies
- `README.md` - This file

## Requirements

- Python 3.8+
- Only standard library (no external dependencies)
  - `json` - Data parsing
  - `re` - Regex extraction
  - `datetime` - Date handling
  - `difflib` - Fuzzy matching

## Installation

```bash
git clone https://github.com/RitwijParmar/bad-deed-validator.git
cd bad-deed-validator
python validator.py
```

## Production Deployment

### Considerations

1. **Error Handling**: Implement custom exception logging
2. **Performance**: Single-pass validation ~10ms per deed
3. **Data Updates**: Support hot-reloading of counties.json
4. **Audit Trail**: Log all rejections with timestamps
5. **Extensibility**: Add more validators as fraud patterns emerge

## Future Enhancements

- [ ] API wrapper (Flask/FastAPI)
- [ ] Additional validators (party name validation, APN format)
- [ ] Batch processing
- [ ] Administrative dashboard for warnings
- [ ] Machine learning for OCR confidence scoring

## License

MIT

## Author

**Ritwij Parmar** - MS Computer Science, University at Buffalo

Engineering Specialization: Backend Systems, Distributed Systems, AI Infrastructure

---

**"In financial systems, paranoia is not a flaw—it's a feature."**
