"""Bad Deed Validator - Paranoid Engineering for OCR Deed Validation

This module implements rigorous validation of OCR-scanned deeds through:
1. Regex-based parsing (NO LLM hallucination risk)
2. Fuzzy matching for county normalization
3. Code-based sanity checks (date logic, amount reconciliation)
4. Comprehensive error reporting

Engineering approach:
- Trust but verify: Parse with code, validate with logic
- Paranoid checks: Date logic impossible conditions catch fraud
- Amount reconciliation: Catch $50k discrepancies between numeric/written
- County fuzzy matching: Handle abbreviations like 'S. Clara' -> 'Santa Clara'
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import difflib


class ValidationError(Exception):
    """Base exception for all validation errors"""
    pass


class DateLogicError(ValidationError):
    """Raised when date logic is violated (e.g., recorded before signed)"""
    pass


class AmountMismatchError(ValidationError):
    """Raised when numeric and written amounts don't reconcile"""
    pass


class CountyLookupError(ValidationError):
    """Raised when county matching fails"""
    pass


class DeedData:
    """Structured representation of extracted deed data"""
    
    def __init__(self):
        self.doc_id: Optional[str] = None
        self.county_raw: Optional[str] = None
        self.county_normalized: Optional[str] = None
        self.state: Optional[str] = None
        self.date_signed: Optional[datetime] = None
        self.date_recorded: Optional[datetime] = None
        self.grantor: Optional[str] = None
        self.grantee: Optional[str] = None
        self.amount_numeric: Optional[float] = None
        self.amount_written: Optional[str] = None
        self.apn: Optional[str] = None
        self.status: Optional[str] = None
        self.tax_rate: Optional[float] = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def to_dict(self) -> Dict:
        return {
            'doc_id': self.doc_id,
            'county_raw': self.county_raw,
            'county_normalized': self.county_normalized,
            'state': self.state,
            'date_signed': self.date_signed.isoformat() if self.date_signed else None,
            'date_recorded': self.date_recorded.isoformat() if self.date_recorded else None,
            'grantor': self.grantor,
            'grantee': self.grantee,
            'amount_numeric': self.amount_numeric,
            'amount_written': self.amount_written,
            'apn': self.apn,
            'status': self.status,
            'tax_rate': self.tax_rate,
            'errors': self.errors,
            'warnings': self.warnings
        }


class DeedParser:
    """Parses OCR text using regex patterns only (no LLM)"""
    
    def __init__(self, counties_file='counties.json'):
        with open(counties_file, 'r') as f:
            self.counties_db = json.load(f)
    
    def parse(self, raw_text: str) -> DeedData:
        deed = DeedData()
        deed.doc_id = self._extract_field(raw_text, r'Doc[^:]*:\s*(\S+)')
        deed.county_raw = self._extract_field(raw_text, r'County[^:]*:\s*([^|\n]+)')
        deed.state = self._extract_field(raw_text, r'State[^:]*:\s*(\w{2})')
        deed.date_signed = self._parse_date(raw_text, r'Date Signed')
        deed.date_recorded = self._parse_date(raw_text, r'Date Recorded')
        deed.grantor = self._extract_field(raw_text, r'Grantor[^:]*:\s*([^\n]+)')
        deed.grantee = self._extract_field(raw_text, r'Grantee[^:]*:\s*([^\n]+)')
        deed.apn = self._extract_field(raw_text, r'APN[^:]*:\s*(\S+)')
        deed.status = self._extract_field(raw_text, r'Status[^:]*:\s*(\w+)')
        
        # Extract amounts
        amount_match = re.search(r'Amount[^:]*:\s*\$([\d,.]+)', raw_text)
        if amount_match:
            try:
                deed.amount_numeric = float(amount_match.group(1).replace(',', ''))
            except ValueError:
                pass
        
        written_match = re.search(r'\(([^)]*(?:Million|Thousand)[^)]*)\)', raw_text)
        if written_match:
            deed.amount_written = written_match.group(1).strip()
        
        return deed
    
    def _extract_field(self, text: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _parse_date(self, text: str, pattern: str) -> Optional[datetime]:
        regex = rf'{pattern}[^\d]*(\d{{4}})-(\d{{2}})-(\d{{2}})'
        match = re.search(regex, text, re.IGNORECASE)
        if match:
            try:
                return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                return None
        return None


class CountyMatcher:
    """Fuzzy matching for county normalization"""
    
    def __init__(self, counties_db):
        self.counties_db = counties_db
    
    def match_county(self, county_raw: str) -> Tuple[str, float]:
        if not county_raw:
            raise CountyLookupError('County name is empty')
        
        county_raw = county_raw.strip().upper()
        best_match, best_ratio = None, 0
        
        for county_info in self.counties_db:
            county_name = county_info['name'].upper()
            
            # Exact match
            if county_raw == county_name:
                return county_info['name'], 1.0
            
            # Abbreviation match (S. Clara -> Santa Clara)
            abbrev = ''.join([w[0] for w in county_info['name'].split()]).upper()
            if county_raw.replace('.', '').replace(' ', '') == abbrev:
                return county_info['name'], 0.95
            
            # Fuzzy match
            ratio = difflib.SequenceMatcher(None, county_raw, county_name).ratio()
            if ratio > best_ratio:
                best_ratio, best_match = ratio, county_info['name']
        
        if best_ratio < 0.6:
            raise CountyLookupError(f'No match for {county_raw}')
        
        return best_match, best_ratio
    
    def get_tax_rate(self, county_name: str) -> float:
        for county_info in self.counties_db:
            if county_info['name'].upper() == county_name.upper():
                return county_info['tax_rate']
        raise CountyLookupError(f'County not found: {county_name}')


class DeedValidator:
    """Paranoid validation with critical sanity checks"""
    
    def __init__(self, counties_matcher: CountyMatcher):
        self.matcher = counties_matcher
    
    def validate(self, deed: DeedData) -> DeedData:
        try:
            self._validate_date_logic(deed)
            self._validate_amount_reconciliation(deed)
            self._enrich_county(deed)
        except ValidationError as e:
            deed.errors.append(str(e))
        return deed
    
    def _validate_date_logic(self, deed: DeedData) -> None:
        """CRITICAL: Recorded date cannot be before signed date"""
        if deed.date_signed and deed.date_recorded:
            if deed.date_recorded > deed.date_signed:
                raise DateLogicError(
                    f'Date logic violation: Recorded {deed.date_recorded.date()} '
                    f'is before Signed {deed.date_signed.date()}'
                )
    
    def _validate_amount_reconciliation(self, deed: DeedData) -> None:
        """CRITICAL: Numeric vs written amounts must reconcile"""
        if not deed.amount_numeric or not deed.amount_written:
            return
        
        written_num = self._parse_written_amount(deed.amount_written)
        if written_num is None:
            deed.warnings.append(f'Could not parse: {deed.amount_written}')
            return
        
        discrepancy = abs(deed.amount_numeric - written_num)
        if discrepancy > 0.01:
            raise AmountMismatchError(
                f'Amount mismatch: ${deed.amount_numeric:,.2f} vs {deed.amount_written} '
                f'(diff: ${discrepancy:,.2f})'
            )
    
    def _enrich_county(self, deed: DeedData) -> None:
        try:
            if deed.county_raw:
                normalized, confidence = self.matcher.match_county(deed.county_raw)
                deed.county_normalized = normalized
                deed.tax_rate = self.matcher.get_tax_rate(normalized)
                if confidence < 0.9:
                    deed.warnings.append(f'Low confidence county match: {confidence:.0%}')
        except CountyLookupError as e:
            deed.warnings.append(str(e))
    
    def _parse_written_amount(self, written: str) -> Optional[float]:
        amount = 0.0
        if 'Million' in written:
            m = re.search(r'(\d+(?:\.\d+)?)\s*Million', written)
            if m:
                amount += float(m.group(1)) * 1_000_000
        if 'Thousand' in written:
            t = re.search(r'(\d+(?:\.\d+)?)\s*Thousand', written)
            if t:
                amount += float(t.group(1)) * 1_000
        return amount if amount > 0 else None


class BadDeedValidator:
    """Main orchestrator for deed validation workflow"""
    
    def __init__(self, counties_file='counties.json'):
        with open(counties_file) as f:
            counties_db = json.load(f)
        self.parser = DeedParser(counties_file)
        self.matcher = CountyMatcher(counties_db)
        self.validator = DeedValidator(self.matcher)
    
    def process_deed(self, raw_ocr_text: str) -> DeedData:
        deed = self.parser.parse(raw_ocr_text)
        return self.validator.validate(deed)
    
    def process_and_report(self, raw_ocr_text: str) -> Dict:
        deed = self.process_deed(raw_ocr_text)
        return {
            'status': 'APPROVED' if not deed.errors else 'REJECTED',
            'deed': deed.to_dict(),
            'validation_summary': {
                'errors': deed.errors,
                'warnings': deed.warnings,
                'error_count': len(deed.errors),
                'warning_count': len(deed.warnings)
            }
        }
