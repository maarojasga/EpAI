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
    'Ã–': 'Ö', 'Ãœ': 'Ü', 'Ã¤': 'ä', 'Ã©': 'é',
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

NULL_STRINGS = {'nan','null','missing','unknown','unknow','n/a','none','undefined','','na'}

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

def clean_english_text(v: Any) -> Optional[str]:
    """Clean descriptive text by fixing encoding and removing non-ASCII trailing garbage."""
    s = clean_string(v)
    if not s: return None
    s = fix_encoding(s)
    # Remove non-ASCII characters at the VERY end of the string (junk characters)
    return re.sub(r'[^A-Za-z0-9\s,\.\-/\(\)\+\']+$', '', s).strip() or None

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

def clean_los(v: Any) -> Optional[int]:
    """Extract integer from 'Length of Stay' values (e.g., '9@' -> 9)."""
    s = clean_string(v)
    if not s: return None
    match = re.search(r'^(\d+)', s)
    return int(match.group(1)) if match else None

def format_date_swiss(v: Any) -> Optional[str]:
    """
    Robust date parser supporting multiple formats, returns DD.MM.YYYY [HH:MM:SS].
    """
    s = clean_string(v)
    if not s: return None
    
    # Handle specific 15_02_2026 format found in some files
    s = re.sub(r'(\d{2})_(\d{2})_(\d{4})', r'\1.\2.\3', s)
    
    try:
        if re.match(r'^\d{8}$', s): # YYYYMMDD
            p = pd.to_datetime(s, format='%Y%m%d', errors='coerce')
        elif re.match(r'^\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}$', s): # YYYY-MM-DD
            p = pd.to_datetime(s, dayfirst=False, errors='coerce')
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
    """Extracts numeric part from IDs like 'CASE-0095' or 'PAT-712'."""
    s = clean_string(v)
    if not s: return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
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
