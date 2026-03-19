"""
MappingSession entity - tracks the lifecycle of one file upload + mapping.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import pandas as pd


@dataclass
class ColumnMatch:
    source: str
    target: Optional[str]
    method: str      # exact | alias | fuzzy | ai | user | unmatched
    confidence: float
    description: str = ""


@dataclass
class MappingSession:
    session_id: str
    clinic_id: int
    clinic_name: str
    filepath: str
    filename: str
    file_format: str              # csv | xlsx | pdf
    detected_table: Optional[str]
    detection_confidence: float
    suggested_clinic_name: Optional[str] = None
    auto_matched: List[ColumnMatch] = field(default_factory=list)
    ai_suggestions: List[ColumnMatch] = field(default_factory=list)
    unmatched: List[ColumnMatch] = field(default_factory=list)
    dataframe: Optional[Any] = None   # pd.DataFrame, typed as Any to avoid import issues
    mapped_df: Optional[Any] = None
    rows_loaded: int = 0
    status: str = "pending_review"    # pending_review | loaded | error
    quality_issues: List[Any] = field(default_factory=list)
