"""
validators.py - Data quality checks before loading into staging.

Generates a list of quality issues compatible with tbDataQualityLog.
"""

import pandas as pd
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class QualityIssue:
    """Maps to a row in tbDataQualityLog."""
    entity_name: str       # table name
    field_name: str        # column
    record_key: str        # row identifier
    rule_name: str         # check name
    old_value: str         # problematic value
    new_value: str = ""    # corrected value (if auto-corrected)
    severity: str = "WARNING"  # INFO | WARNING | ERROR
    check_type: str = ""   # null_check | type_check | range_check | format_check
    description: str = ""


def validate_dataframe(df: pd.DataFrame, target_table: str, file_source: str = "") -> List[QualityIssue]:
    """
    Run all quality checks on a mapped DataFrame.
    Returns a list of QualityIssue entries.
    """
    issues: List[QualityIssue] = []

    issues.extend(_check_nulls(df, target_table))
    issues.extend(_check_types(df, target_table))
    issues.extend(_check_duplicates(df, target_table))

    return issues


def _check_nulls(df: pd.DataFrame, table: str) -> List[QualityIssue]:
    """Check for NULL values in critical columns."""
    issues = []
    # Critical columns that should not be null per table
    critical = {
        "tbImportLabsData": ["coCaseId", "coPatientId"],
        "tbImportIcd10Data": ["coCaseId", "coPatientId"],
        "tbImportDeviceMotionData": ["coPatientId", "coTimestamp"],
        "tbImportDevice1HzMotionData": ["coPatientId", "coTimestamp", "coDevice_id"],
        "tbImportMedicationInpatientData": ["coPatientId", "coMedication_name"],
        "tbImportNursingDailyReportsData": ["coPatientId", "coReport_date"],
        "tbCaseData": ["coPatientId"],
    }


    cols_to_check = critical.get(table, [])
    for col in cols_to_check:
        if col in df.columns:
            null_count = df[col].isna().sum()
            if null_count > 0:
                null_rows = df[df[col].isna()].index.tolist()[:5]  # first 5
                issues.append(QualityIssue(
                    entity_name=table,
                    field_name=col,
                    record_key=f"rows: {null_rows}",
                    rule_name="NOT_NULL_CHECK",
                    old_value=f"{null_count} null values",
                    severity="ERROR" if null_count > 10 else "WARNING",
                    check_type="null_check",
                    description=f"Critical column '{col}' has {null_count} null values"
                ))

    return issues


def _check_types(df: pd.DataFrame, table: str) -> List[QualityIssue]:
    """Check for unexpected data types in columns."""
    issues = []

    # Columns expected to hold datetime values
    datetime_cols = {
        "coTimestamp", "coSpecimen_datetime", "coAdmission_date",
        "coDischarge_date", "coAdmission_datetime", "coDischarge_datetime",
        "coOrder_start_datetime", "coOrder_stop_datetime",
        "coReport_date", "coDateOfBirth", "coE2I223", "coE2I228",
    }

    for col in df.columns:
        if col in datetime_cols:
            # Try to detect non-parseable dates
            non_null = df[col].dropna()
            if len(non_null) > 0 and non_null.dtype == object:
                sample = non_null.head(100)
                bad_dates = []
                for idx, val in sample.items():
                    try:
                        pd.to_datetime(val)
                    except (ValueError, TypeError):
                        bad_dates.append(str(val))
                if bad_dates:
                    issues.append(QualityIssue(
                        entity_name=table,
                        field_name=col,
                        record_key=f"sample of {len(bad_dates)} bad dates",
                        rule_name="DATE_FORMAT_CHECK",
                        old_value=str(bad_dates[:3]),
                        severity="WARNING",
                        check_type="format_check",
                        description=f"Column '{col}' has unparseable date values"
                    ))

    return issues


def _check_duplicates(df: pd.DataFrame, table: str) -> List[QualityIssue]:
    """Check for full duplicate rows."""
    issues = []
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        issues.append(QualityIssue(
            entity_name=table,
            field_name="*",
            record_key=f"{dup_count} duplicates",
            rule_name="DUPLICATE_ROW_CHECK",
            old_value=f"{dup_count} duplicate rows found",
            severity="INFO" if dup_count < 5 else "WARNING",
            check_type="duplicate_check",
            description=f"Found {dup_count} fully duplicate rows"
        ))

    return issues
