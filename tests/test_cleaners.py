import pytest
from infrastructure.mapping_engine.cleaners import (
    clean_sex, extract_numeric_id, clean_numeric, 
    format_date_swiss, fix_encoding, clean_icd_code
)

def test_clean_sex():
    assert clean_sex("männlich") == "M"
    assert clean_sex("weiblich") == "F"
    assert clean_sex("Male") == "M"
    assert clean_sex("female") == "F"
    assert clean_sex("M") == "M"
    assert clean_sex("F") == "F"
    assert clean_sex("Ã¤nnlich") == "M" # Encoding fix
    assert clean_sex("Unknown") is None

def test_extract_numeric_id():
    assert extract_numeric_id("CASE-0095") == 95
    assert extract_numeric_id("PAT712") == 712
    assert extract_numeric_id("123.0") == 123
    assert extract_numeric_id("  456  ") == 456
    assert extract_numeric_id("NoID") is None

def test_clean_numeric():
    assert clean_numeric("12.5 mmol/L") == "12.5"
    assert clean_numeric("100") == "100"
    assert clean_numeric("-5") is None # Negative anomaly
    assert clean_numeric("Invalid") is None
    assert clean_numeric("0.0") == "0"

def test_format_date_swiss():
    assert format_date_swiss("2024-03-20") == "20.03.2024"
    assert format_date_swiss("20.03.2024") == "20.03.2024"
    assert format_date_swiss("20240320") == "20.03.2024"
    assert format_date_swiss("20_03_2024") == "20.03.2024"
    assert format_date_swiss("20.03.2024 14:30:00") == "20.03.2024 14:30:00"

def test_fix_encoding():
    assert fix_encoding("Ã¶") == "ö"
    assert fix_encoding("Ã¼") == "ü"
    assert fix_encoding("ÃŸ") == "ß"

def test_clean_icd_code():
    assert clean_icd_code("A00.0+") == "A00.0"
    assert clean_icd_code("8-98f*") == "8-98f"
