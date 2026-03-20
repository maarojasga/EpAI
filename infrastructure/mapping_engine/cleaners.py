"""
cleaners.py - Specialized data cleaning and normalization logic extracted from 
harmonization notebooks (e.g., icd_ops.ipynb).
"""

import re
import pandas as pd
from typing import Any, Optional

# --- CONFIG & CONSTANTS ---

ENCODING_FIXES = {
    'Ã¶': 'ö', 'Ã¼': 'ü', 'ÃŸ': 'ß', 'Ã„': 'Ä',
    'Ã–': 'Ö', 'Ãœ': 'Ü', 'Ã': 'ä', 'Ã©': 'é',
    'HHü': 'HH', 'LLß': 'LL', 'H@': 'H',
}

WARD_CANONICAL = {
    'chirurgie':       'Chirurgie',
    'geriatrie':       'Geriatrie',
    'innere medizin':  'Innere Medizin',
    'intensivstation': 'Intensivstation',
    'kardiologie':     'Kardiologie',
    'neurologie':      'Neurologie',
    'pneumologie':     'Pneumologie',
}

NULL_STRINGS = {
    'nan', 'null', 'missing', 'unknown', 'unknow', 'n/a', 'none', 
    'undefined', '', 'na', 'unkown', 'not applicable'
}

VALID_LAB_FLAGS = {'H', 'L', 'HH', 'LL'}

SYNTHETIC_CASE_PREFIX = 9_000_000

# --- CORE CLEANING FUNCTIONS ---

def clean_string(v: Any) -> Optional[str]:
    """Basic string cleanup and null handling."""
    if pd.isna(v): return None
    s = str(v).strip()
    return None if s.lower() in NULL_STRINGS else s

def fix_encoding(s: str) -> str:
    """Fix common broken UTF-8 characters as found in the data files."""
    for broken, correct in ENCODING_FIXES.items():
        s = s.replace(broken, correct)
    return s

def clean_icd_code(v: Any) -> Optional[str]:
    """Clean ICD/OPS codes: fix encoding and remove trailing special characters."""
    s = clean_string(v)
    if not s: return None
    s = fix_encoding(s)
    # Only keep Alphanumeric, dot, and dash
    return re.sub(r'[^A-Za-z0-9\.\-]+$', '', s).strip() or None

def clean_sex(v: Any) -> Optional[str]:
    """
    Standardize sex to 'M' or 'F'.
    Handles English (male/female), German (männlich/weiblich), 
    and common encoding artifacts.
    """
    s = clean_string(v)
    if not s: return None
    s = fix_encoding(s)
    # Remove trailing garbage
    s = re.sub(r'[^A-Za-z]+$', '', s).strip().lower()
    
    if s in ('m', 'male', 'männlich', 'maennlich', 'mann', 'mä', 'mö', 'mü', 'mß') or \
       s.startswith('male') or s.startswith('männ') or s.startswith('maenn'):
        return 'M'
    if s in ('f', 'female', 'weiblich', 'frau', 'w', 'fö', 'fä', 'fü') or \
       s.startswith('female') or s.startswith('weibl'):
        return 'F'
    return None

def clean_lab_flag(v: Any) -> Optional[str]:
    """Extract and validate lab flags (H, L, HH, LL)."""
    s = clean_string(v)
    if not s: return None
    s = fix_encoding(s).strip().upper()
    # Match start of string for H/L/HH/LL
    match = re.match(r'^(H{1,2}|L{1,2})', s)
    if match:
        flag = match.group(1)
        return flag if flag in VALID_LAB_FLAGS else None
    return None

def clean_numeric(v: Any) -> Optional[str]:
    """
    Cleans numeric strings: fix encoding, strip non-numeric suffixes,
    and returns as string. Returns None for negative values (anomalies).
    """
    s = clean_string(v)
    if not s: return None
    s = fix_encoding(s)
    # Remove trailing unit characters or garbage (e.g. "12.5 mmol/L" -> "12.5")
    s = re.sub(r'[^0-9\.\-]+$', '', s).strip()
    try:
        f = float(s)
        # Handle special -0 cases
        if f == -0.0 or s in ('-0', '-0.0', '-0.00'):
            return "0"
        # Negative values are usually data errors in labs/age
        if f < 0:
            return None
        return str(f) if '.' in s else str(int(f))
    except (ValueError, TypeError):
        return None

def clean_age(v: Any) -> Optional[int]:
    """Age in years: integers between 0 and 110."""
    num_str = clean_numeric(v)
    if not num_str: return None
    try:
        age = int(float(num_str))
        return age if 0 <= age <= 110 else None
    except:
        return None

def clean_ward(v: Any) -> Optional[str]:
    """Clean and standardize ward names to canonical German names."""
    s = clean_string(v)
    if not s: return None
    s = fix_encoding(s)
    # Remove trailing garbage
    s = re.sub(r'[^A-Za-z0-9äöüÄÖÜßéàè\s\-/]+$', '', s).strip()
    s_lower = s.lower()
    for key, canonical in WARD_CANONICAL.items():
        if s_lower.startswith(key) or key in s_lower:
            return canonical
    return s or None

def format_date_swiss(v: Any) -> Optional[str]:
    """
    Robust date parser supporting multiple formats, returns DD.MM.YYYY [HH:MM:SS].
    """
    s = clean_string(v)
    if not s: return None
    
    # Handle specific separators
    s = re.sub(r'(\d{2})_(\d{2})_(\d{4})', r'\1.\2.\3', s)
    
    try:
        # 1. YYYYMMDD
        if re.match(r'^\d{8}$', s): 
            p = pd.to_datetime(s, format='%Y%m%d', errors='coerce')
        # 2. YYYY-MM-DD (ISOish)
        elif re.match(r'^\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}', s): 
            p = pd.to_datetime(s, dayfirst=False, errors='coerce')
        # 3. DD.MM.YYYY (European/Swiss)
        elif re.match(r'^\d{1,2}[/\\.]\d{1,2}[/\\.]\d{4}', s):
            p = pd.to_datetime(s, dayfirst=True, errors='coerce')
        else:
            p = pd.to_datetime(s, dayfirst=True, errors='coerce')
            
        if not pd.isna(p):
            if p.hour or p.minute or p.second:
                return p.strftime('%d.%m.%Y %H:%M:%S')
            return p.strftime('%d.%m.%Y')
    except:
        pass
    return None

def extract_numeric_id(v: Any) -> Optional[int]:
    """Extracts numeric part from IDs like 'CASE-0095' or 'PATCASE712'."""
    s = clean_string(v)
    if not s: return None
    try:
        # Direct float conversion if possible
        return int(float(s))
    except (ValueError, TypeError):
        # Extract digits from string
        nums = re.findall(r'\d+', s)
        return int(''.join(nums)) if nums else None

def generate_synthetic_case_id(patient_id: Optional[int]) -> Optional[int]:
    """Generates a synthetic CaseID if missing but PatientID exists."""
    if patient_id is not None:
        return SYNTHETIC_CASE_PREFIX + patient_id
    return None

def is_icd_code(v: Any) -> bool:
    """Check if a string matches the ICD-10 pattern (e.g. A00.0)."""
    c = clean_icd_code(v)
    if not c: return False
    return bool(re.match(r'^[A-Z][0-9]{2}[0-9.]*[A-Za-z0-9.]*$', c))

def is_ops_code(v: Any) -> bool:
    """Check if a string matches the OPS pattern (e.g. 8-98f)."""
    c = clean_icd_code(v)
    if not c: return False
    return bool(re.match(r'^[0-9][A-Za-z0-9]*-[A-Za-z0-9.]+$', c))


# --- MEDICATION CLEANERS ---

VALID_RECORD_TYPE  = {'ORDER','ADMIN','CHANGE'}
VALID_ORDER_STATUS = {'active','cancelled','stopped','on-hold','completed'}
VALID_ADMIN_STATUS = {'administered','refused','partial','held','missed','given'}
VALID_ROUTE        = {'SC','IV','PO','IM','INH','TD','SL','PR','TOP','NG','NAS'}

def _clean_status_generic(v: Any, valid_set: set) -> Optional[str]:
    """Helper to strictly normalize statuses against a set of valid strings."""
    s = clean_string(v)
    if not s: return None
    s = fix_encoding(s)
    # Strip garbage chars from ends but allow inner hyphens
    s = re.sub(r'[^A-Za-z0-9\-]+$', '', s).strip().rstrip('\t\n\r')
    for val in valid_set:
        if s.lower() == val.lower(): return val
    return None

def clean_record_type(v: Any) -> Optional[str]:
    return _clean_status_generic(v, VALID_RECORD_TYPE)

def clean_order_status(v: Any) -> Optional[str]:
    return _clean_status_generic(v, VALID_ORDER_STATUS)

def clean_admin_status(v: Any) -> Optional[str]:
    return _clean_status_generic(v, VALID_ADMIN_STATUS)

def clean_route(v: Any) -> Optional[str]:
    """Normalize administration route (e.g., PO, IV)."""
    s = clean_string(v)
    if not s: return None
    s = fix_encoding(s)
    s = re.sub(r'[^A-Za-z]+$', '', s).strip().upper()
    return s if s in VALID_ROUTE else (s if s else None)

def clean_prn(v: Any) -> Optional[str]:
    """Normalize boolean 'Pro Re Nata' (as-needed) strings to '0' or '1'."""
    s = clean_string(v)
    if not s: return None
    s = fix_encoding(s)
    s = re.sub(r'[^A-Za-z0-9]+$', '', s).strip().upper()
    if s in ('1','PRN','YES','JA','TRUE','BEDARF'): return '1'
    if s in ('0','NO','NEIN','FALSE'):              return '0'
    try: 
        return '1' if int(float(s)) == 1 else '0'
    except: 
        return None

# --- epaAC SPECIALIZED CLEANING ---

class EpaAcLookup:
    """Helper to resolve SID codes to human-readable names using a catalog CSV."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EpaAcLookup, cls).__new__(cls)
            cls._instance.sid_map = {}
            cls._instance.loaded = False
        return cls._instance

    def load(self, catalog_path: str):
        if self.loaded: return
        try:
            import csv
            with open(catalog_path, encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    sid = row.get("ItmSID", "").strip()
                    en = row.get("ItmName255_EN", "").strip()
                    de = row.get("ItmName255_DE", "").strip()
                    if sid:
                        self.sid_map[sid] = en or de or sid
            self.loaded = True
        except Exception as e:
            print(f"Warning: Could not load epaAC catalog: {e}")

    def resolve(self, val: Any) -> str:
        s = str(val).strip()
        if not s or s.lower() in NULL_STRINGS: return ""
        return self.sid_map.get(s, s)

_epaac_lookup = EpaAcLookup()

def clean_epaac_val(v: Any, catalog_path: Optional[str] = None) -> Optional[str]:
    """
    Resolves an epaAC SID value to its human-readable name.
    If catalog_path is provided, it attempts to load it first.
    """
    if catalog_path:
        _epaac_lookup.load(catalog_path)
    
    res = _epaac_lookup.resolve(v)
    return res if res else None

