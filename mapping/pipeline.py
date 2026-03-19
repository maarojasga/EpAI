"""
pipeline.py - Main orchestrator for the Smart Health Data Mapping pipeline.

Flow:
1. Clinic selects itself (or creates a new one)
2. Clinic uploads a file
3. System detects format and target table
4. System auto-matches columns (exact, alias, fuzzy)
5. Unmatched columns go to AI for interpretation
6. User reviews AI suggestions (accept/reject)
7. Data is mapped, validated, and loaded to staging
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from .detect import detect, DetectionResult
from .matcher import match_columns, MappingResult, ColumnMatch
from .validators import validate_dataframe, QualityIssue
from .profiles import STAGING_SCHEMAS


# ---------------------------------------------------------------------------
# In-memory staging database (dict of DataFrames)
# ---------------------------------------------------------------------------

STAGING_DB: Dict[str, pd.DataFrame] = {}

# In-memory clinic list
CLINICS: List[Dict[str, Any]] = []


def _init_staging():
    """Initialize empty staging tables."""
    for table_name, schema in STAGING_SCHEMAS.items():
        if table_name not in STAGING_DB:
            STAGING_DB[table_name] = pd.DataFrame(columns=schema["columns"])

_init_staging()


# ---------------------------------------------------------------------------
# Clinic management
# ---------------------------------------------------------------------------

def list_clinics() -> List[Dict[str, Any]]:
    """Return list of registered clinics."""
    return CLINICS


def get_or_create_clinic(name: str, location: str = "", system_type: str = "") -> Dict[str, Any]:
    """Find a clinic by name or create a new one."""
    for clinic in CLINICS:
        if clinic["name"].lower() == name.lower():
            return clinic

    new_clinic = {
        "id": len(CLINICS) + 1,
        "name": name,
        "location": location,
        "system_type": system_type,
    }
    CLINICS.append(new_clinic)
    return new_clinic


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Complete result of processing a file."""
    clinic: Dict[str, Any]
    detection: DetectionResult
    mapping: MappingResult
    quality_issues: List[QualityIssue] = field(default_factory=list)
    mapped_df: Optional[pd.DataFrame] = None
    rows_loaded: int = 0
    status: str = "pending_review"  # pending_review | loaded | error


# ---------------------------------------------------------------------------
# Main pipeline functions
# ---------------------------------------------------------------------------

def process_file(
    filepath: str,
    clinic_name: str,
    clinic_location: str = "",
    target_table: str = None,
    use_ai: bool = True,
    models_dir: str = None,
) -> PipelineResult:
    """
    Step 1-5 of the pipeline: detect, match, suggest.
    Returns a PipelineResult with mapping suggestions for user review.
    """
    # Get or create clinic
    clinic = get_or_create_clinic(clinic_name, clinic_location)

    # Detect format, read data, identify table
    detection = detect(filepath)

    if detection.dataframe is None or detection.dataframe.empty:
        return PipelineResult(
            clinic=clinic,
            detection=detection,
            mapping=MappingResult(target_table=target_table or "unknown"),
            status="error",
        )

    # Use user-specified table or auto-detected
    resolved_table = target_table or detection.detected_table
    if not resolved_table:
        return PipelineResult(
            clinic=clinic,
            detection=detection,
            mapping=MappingResult(target_table="unknown"),
            status="error",
        )

    # Match columns
    mapping = match_columns(
        source_headers=list(detection.dataframe.columns),
        target_table=resolved_table,
        use_ai=use_ai,
        models_dir=models_dir,
    )

    return PipelineResult(
        clinic=clinic,
        detection=detection,
        mapping=mapping,
        status="pending_review",
    )


def apply_mapping(
    result: PipelineResult,
    user_decisions: Dict[str, Optional[str]] = None,
) -> PipelineResult:
    """
    Step 6-7: Apply user decisions and load data.

    user_decisions: dict mapping source_header -> accepted_target_column (or None to reject).
    If None, all auto_matched are used and ai_suggestions are rejected.
    """
    if result.detection.dataframe is None:
        result.status = "error"
        return result

    df = result.detection.dataframe.copy()

    # Build final column map: source -> target
    col_map = {}

    # Auto-matched columns are always accepted
    for match in result.mapping.auto_matched:
        if match.target:
            col_map[match.source] = match.target

    # AI suggestions: apply user decisions
    if user_decisions:
        for match in result.mapping.ai_suggestions:
            decision = user_decisions.get(match.source)
            if decision:  # user accepted with a target
                col_map[match.source] = decision
            # else: rejected, column stays unmapped (NULL)

    # Rename columns using the map
    mapped_df = pd.DataFrame()
    for source_col, target_col in col_map.items():
        if source_col in df.columns:
            mapped_df[target_col] = df[source_col]

    # Ensure all target table columns exist (fill missing with NaN)
    schema = STAGING_SCHEMAS.get(result.mapping.target_table, {})
    for tc in schema.get("columns", []):
        if tc != "coId" and tc not in mapped_df.columns:
            mapped_df[tc] = None

    result.mapped_df = mapped_df

    # Validate
    result.quality_issues = validate_dataframe(
        mapped_df, result.mapping.target_table
    )

    # Load to staging
    table_name = result.mapping.target_table
    if table_name in STAGING_DB:
        STAGING_DB[table_name] = pd.concat(
            [STAGING_DB[table_name], mapped_df], ignore_index=True
        )
        result.rows_loaded = len(mapped_df)
        result.status = "loaded"
    else:
        result.status = "error"

    return result


def get_staging_summary() -> Dict[str, int]:
    """Return row counts for all staging tables."""
    return {table: len(df) for table, df in STAGING_DB.items()}


# ---------------------------------------------------------------------------
# CLI helper for quick testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m mapping.pipeline <filepath> <clinic_name>")
        sys.exit(1)

    filepath = sys.argv[1]
    clinic_name = sys.argv[2]

    print(f"Processing: {filepath}")
    print(f"Clinic: {clinic_name}")
    print("-" * 60)

    result = process_file(filepath, clinic_name, use_ai=False)

    print(f"Format: {result.detection.format}")
    print(f"Delimiter: {result.detection.delimiter}")
    print(f"Headers: {len(result.detection.headers)}")
    print(f"Detected table: {result.detection.detected_table} ({result.detection.confidence:.0%})")
    print()

    print(f"AUTO-MATCHED ({len(result.mapping.auto_matched)}):")
    for m in result.mapping.auto_matched:
        print(f"  [OK] {m.source:40s} -> {m.target:40s} ({m.method}, {m.confidence:.0%})")

    print(f"\nAI SUGGESTIONS ({len(result.mapping.ai_suggestions)}):")
    for m in result.mapping.ai_suggestions:
        print(f"  [??] {m.source:40s} -> {m.target:40s} ({m.confidence:.0%}) {m.description}")

    print(f"\nUNMATCHED ({len(result.mapping.unmatched)}):")
    for m in result.mapping.unmatched:
        print(f"  [--] {m.source}")

    # Auto-load without AI suggestions
    result = apply_mapping(result)
    print(f"\nLoaded {result.rows_loaded} rows into {result.mapping.target_table}")
    print(f"Quality issues: {len(result.quality_issues)}")
    for issue in result.quality_issues:
        print(f"  [{issue.severity}] {issue.field_name}: {issue.description}")
