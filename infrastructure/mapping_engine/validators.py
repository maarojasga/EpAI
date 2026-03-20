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
    record_key: str        # row identifier (e.g. CaseId or Row Index)
    rule_name: str         # check name (e.g. SEX_NORMALIZATION)
    old_value: str         # original problematic value
    new_value: str = ""    # corrected value
    severity: str = "WARNING"  # INFO | WARNING | ERROR | CLEANED
    check_type: str = ""   # null_check | type_check | range_check | format_check | cleaning_audit
    description: str = ""  # Justification for the change


def validate_dataframe(df: pd.DataFrame, target_table: str, file_source: str = "") -> List[QualityIssue]:
    """
    Run all quality checks on a mapped DataFrame.
    Returns a list of QualityIssue entries.
    """
    issues: List[QualityIssue] = []

    issues.extend(_check_nulls(df, target_table))
    issues.extend(_check_types(df, target_table))
    issues.extend(_check_duplicates(df, target_table))
    issues.extend(_check_date_sequence(df, target_table))
    issues.extend(_check_clinical_ranges(df, target_table))
    issues.extend(_check_negative_labs(df, target_table))
    issues.extend(_check_lab_flags(df, target_table))

    return issues


def _check_negative_labs(df: pd.DataFrame, table: str) -> List[QualityIssue]:
    """Check for negative values in numeric lab results (data errors)."""
    issues = []
    if table != "tbImportLabsData":
        return issues
        
    for col in df.columns:
        if col.startswith("co") and any(x in col.lower() for x in ["mmol_l", "mg_dl", "g_dl", "10e9_l", "u_l"]):
            series = pd.to_numeric(df[col], errors='coerce').dropna()
            negatives = series[series < 0]
            if not negatives.empty:
                issues.append(QualityIssue(
                    entity_name=table,
                    field_name=col,
                    record_key=f"{len(negatives)} negative values",
                    rule_name="NEGATIVE_VALUE_CHECK",
                    old_value=f"Samples: {negatives.head(3).tolist()}",
                    severity="ERROR",
                    check_type="range_check",
                    description=f"Detected {len(negatives)} negative values in laboratory result column '{col}'."
                ))
    return issues


def _check_lab_flags(df: pd.DataFrame, table: str) -> List[QualityIssue]:
    """Check that lab flags are H, L, HH, or LL (normalized)."""
    issues = []
    if table != "tbImportLabsData":
        return issues
        
    valid_flags = {'H', 'L', 'HH', 'LL', None}
    for col in df.columns:
        if col.endswith("_flag"):
            invalid = df[~df[col].isin(valid_flags)][col].dropna().unique()
            if len(invalid) > 0:
                issues.append(QualityIssue(
                    entity_name=table,
                    field_name=col,
                    record_key=f"invalid flags: {invalid}",
                    rule_name="LAB_FLAG_CHECK",
                    old_value=str(invalid),
                    severity="WARNING",
                    check_type="format_check",
                    description=f"Column '{col}' contains unrecognized flags outside of standard H, L, HH, LL."
                ))
    return issues


def _check_date_sequence(df: pd.DataFrame, table: str) -> List[QualityIssue]:
    """Check that admission dates are before discharge dates."""
    issues = []
    
    date_pairs = [
        ("coAdmission_date", "coDischarge_date"),
        ("coAdmission_datetime", "coDischarge_datetime"),
        ("coOrder_start_datetime", "coOrder_stop_datetime")
    ]
    
    for start_col, end_col in date_pairs:
        if start_col in df.columns and end_col in df.columns:
            # Drop nulls and non-dates for this check
            temp_df = df[[start_col, end_col]].dropna()
            if not temp_df.empty:
                try:
                    start_dt = pd.to_datetime(temp_df[start_col], errors='coerce')
                    end_dt = pd.to_datetime(temp_df[end_col], errors='coerce')
                    
                    # Find where end is before start
                    invalid_mask = end_dt < start_dt
                    invalid_count = invalid_mask.sum()
                    
                    if invalid_count > 0:
                        issues.append(QualityIssue(
                            entity_name=table,
                            field_name=f"{start_col} vs {end_col}",
                            record_key="date_sequence_error",
                            rule_name="CHRONOLOGY_CHECK",
                            old_value=f"{invalid_count} records",
                            severity="ERROR",
                            check_type="logic_check",
                            description=f"Discharge date is before Admission date in {invalid_count} records."
                        ))
                except:
                    pass
    return issues


def _check_clinical_ranges(df: pd.DataFrame, table: str) -> List[QualityIssue]:
    """Check lab values against standard clinical reference ranges."""
    issues = []
    if table != "tbImportLabsData":
        return issues
        
    # Standard ranges (Normal values)
    ranges = {
        "coSodium_mmol_L": (135, 145),
        "coPotassium_mmol_L": (3.5, 5.0),
        "coHemoglobin_g_dL": (12, 18),
        "coWbc_10e9_L": (4.0, 11.0),
        "coPlatelets_10e9_L": (150, 450),
        "coGlucose_mg_dL": (70, 140),
        "coCreatinine_mg_dL": (0.6, 1.2),
    }
    
    for col, (low, high) in ranges.items():
        if col in df.columns:
            series = pd.to_numeric(df[col], errors='coerce').dropna()
            if not series.empty:
                out_of_range = series[(series < low) | (series > high)]
                count = len(out_of_range)
                if count > 0:
                    issues.append(QualityIssue(
                        entity_name=table,
                        field_name=col,
                        record_key=f"clinical_anomaly: {count} cases",
                        rule_name="CLINICAL_RANGE_CHECK",
                        old_value=f"Min: {series.min()}, Max: {series.max()}",
                        severity="WARNING",
                        check_type="range_check",
                        description=f"Detected {count} values outside normal range [{low} - {high}]. Potential clinical anomaly."
                    ))
                    
    return issues


def _check_nulls(df: pd.DataFrame, table: str) -> List[QualityIssue]:
    """Check for NULL values in critical columns."""
    issues = []
    # Critical columns that should not be null per table
    critical = {
        "tbImportLabsData": ["coCaseId"],
        "tbImportIcd10Data": ["coCaseId"],
        "tbImportDeviceMotionData": ["coPatient_id", "coTimestamp"],
        "tbImportDevice1HzMotionData": ["coPatient_id", "coTimestamp", "coDevice_id"],
        "tbImportMedicationInpatientData": ["coPatient_id", "coMedication_name"],
        "tbImportNursingDailyReportsData": ["coPatient_id", "coReport_date"],
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
