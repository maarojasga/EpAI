"""
detect.py — Auto-detect file format, delimiter, encoding, and target table.

Given a file path, returns:
- format: csv | xlsx | pdf
- delimiter: , | ; | tab (for CSV)
- encoding: utf-8, latin-1, etc.
- headers: list of column names
- detected_table: best-matching staging table (or None)
- confidence: 0.0–1.0 for table detection
"""

import os
import csv
import io
import pandas as pd
import re
from dataclasses import dataclass, field
from typing import List, Optional

from infrastructure.mapping_engine.profiles import STAGING_SCHEMAS


@dataclass
class DetectionResult:
    filepath: str
    format: str                       # csv, xlsx, pdf
    delimiter: Optional[str] = None   # only for csv
    encoding: str = "utf-8"
    headers: List[str] = field(default_factory=list)
    detected_table: Optional[str] = None
    confidence: float = 0.0
    suggested_clinic_name: Optional[str] = None
    dataframe: Optional[pd.DataFrame] = None  # loaded data


def _detect_encoding(filepath: str) -> str:
    """Try common encodings; return the one that works."""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                f.read(4096)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "latin-1"  # safe fallback


def _detect_delimiter(filepath: str, encoding: str) -> str:
    """Sniff the CSV delimiter from the first few lines."""
    with open(filepath, "r", encoding=encoding) as f:
        sample = f.read(8192)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        # Heuristic: count occurrences in the first line
        first_line = sample.split("\n")[0]
        if first_line.count(";") > first_line.count(","):
            return ";"
        return ","


def _fingerprint_score(headers: List[str], fingerprint: set) -> float:
    """Score how well a set of headers matches a table fingerprint."""
    # Normalize: join all headers, keep underscores for substring matching
    headers_text = " ".join(h.lower() for h in headers)
    # Also create a version without underscores for fuzzy keyword matching
    headers_text_no_us = headers_text.replace("_", "")

    matches = 0
    for keyword in fingerprint:
        kw_lower = keyword.lower()
        kw_no_us = kw_lower.replace("_", "")
        # Try both: with underscores (exact substring) and without (fuzzy)
        if kw_lower in headers_text or kw_no_us in headers_text_no_us:
            matches += 1

    if len(fingerprint) == 0:
        return 0.0
    return matches / len(fingerprint)


def _detect_table(headers: List[str]) -> tuple:
    """Find the best-matching staging table for a set of headers."""
    best_table = None
    best_score = 0.0

    for table_name, schema in STAGING_SCHEMAS.items():
        score = _fingerprint_score(headers, schema["fingerprint"])
        if score > best_score:
            best_score = score
            best_table = table_name

    return best_table, best_score


def _extract_clinic_name(filepath: str) -> Optional[str]:
    """Try to extract a clinic name from the filename (e.g. 'clinic_1_...')."""
    filename = os.path.basename(filepath)
    # Match 'clinic_1', 'Clinic_2', 'clinic1', etc.
    match = re.search(r"(clinic)[_ \-]*(\d+)", filename, re.IGNORECASE)
    if match:
        return f"Clinic {match.group(2)}"
    return None


def detect(filepath: str) -> DetectionResult:
    """
    Auto-detect everything about a file and load it into a DataFrame.
    """
    ext = os.path.splitext(filepath)[1].lower()
    result = DetectionResult(filepath=filepath, format="unknown")

    if ext == ".csv":
        result.format = "csv"
        result.encoding = _detect_encoding(filepath)
        result.delimiter = _detect_delimiter(filepath, result.encoding)

        try:
            df = pd.read_csv(
                filepath,
                delimiter=result.delimiter,
                encoding=result.encoding,
                low_memory=False,
            )
            result.headers = list(df.columns)
            result.dataframe = df
        except Exception as e:
            result.headers = []
            print(f"[detect] Error reading CSV: {e}")

    elif ext in (".xlsx", ".xls"):
        result.format = "xlsx"
        try:
            df = pd.read_excel(filepath)
            result.headers = list(df.columns)
            result.dataframe = df
        except Exception as e:
            result.headers = []
            print(f"[detect] Error reading Excel: {e}")

    elif ext == ".pdf":
        result.format = "pdf"
        # PDF handling is delegated to pdf_extract.py
        # We just mark the format here
        return result

    else:
        print(f"[detect] Unsupported format: {ext}")
        return result

    # Detect target table from headers
    if result.headers:
        result.detected_table, result.confidence = _detect_table(result.headers)

    # SPECIAL HANDLING FOR epaAC (Dual Headers)
    # If tbImportEpaAcData detected, check if row 1 contains IIDs
    if result.detected_table == "tbImportEpaAcData" and result.dataframe is not None and len(result.dataframe) > 0:
        row1 = list(result.dataframe.iloc[0].values)
        row1_str = " ".join(str(c) for c in row1)
        if re.search(r"E\d_I_\d+", row1_str, re.IGNORECASE):
            # Promote row 1 to headers
            new_headers = [str(c).strip() for c in row1]
            # Rename dataframe columns
            result.dataframe.columns = new_headers
            # Drop the row that we used as header
            result.dataframe = result.dataframe.iloc[1:].reset_index(drop=True)
            result.headers = new_headers
            # Re-detect to confirm
            result.detected_table, result.confidence = _detect_table(result.headers)

    # Extract clinic name from filename
    result.suggested_clinic_name = _extract_clinic_name(filepath)

    return result

