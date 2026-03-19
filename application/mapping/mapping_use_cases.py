"""
mapping_use_cases.py - Application-layer use cases for the mapping pipeline.
"""
import os
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd

from domain.entities.clinic import Clinic
from domain.entities.mapping_session import MappingSession, ColumnMatch
from domain.entities.quality_issue import QualityIssue
from infrastructure.storage import in_memory_store as store
from infrastructure.mapping_engine.detect import detect
from infrastructure.mapping_engine.matcher import match_columns
from infrastructure.mapping_engine.validators import validate_dataframe
from infrastructure.mapping_engine.profiles import STAGING_SCHEMAS


def process_upload(
    filepath: str,
    clinic: Clinic,
    target_table: Optional[str] = None,
    use_ai: bool = True,
    models_dir: Optional[str] = None,
) -> MappingSession:
    """
    Detect the file format, match columns, and persist a pending session.
    """
    detection = detect(filepath)

    # Special handling for PDFs/Unstructured text
    if detection.format == "pdf" or (detection.dataframe is None or detection.dataframe.empty):
        from infrastructure.mapping_engine.pdf_extract import process_unstructured_file
        extracted_data = process_unstructured_file(filepath, models_dir=models_dir)
        
        if extracted_data:
            # Convert JSON keys to our canonical staging column names
            # Map common LLM output keys to our schema
            mapping_dict = {
                "patient_name": "coPatientName",
                "case_id": "coCaseId",
                "admission_date": "coAdmission_date",
                "diagnoses": "coPrimary_icd10_code",
                "medications": "coMedicationInpatient",
                "vitals": "coVitals" # We'll handle flattening later or just keep as string
            }
            
            flat_data = {}
            for k, v in extracted_data.items():
                target = mapping_dict.get(k, k) # Use map or keep original
                # If list, join by semicolon
                if isinstance(v, list):
                    flat_data[target] = "; ".join(v)
                elif isinstance(v, dict):
                    flat_data[target] = str(v)
                else:
                    flat_data[target] = v
            
            detection.dataframe = pd.DataFrame([flat_data])
            detection.detected_table = "tbImportIcd10Data" # Default for reports
            detection.confidence = 0.9 # High confidence because IA extracted it
    
    if detection.dataframe is None or detection.dataframe.empty:
        session = MappingSession(
            session_id=uuid.uuid4().hex,
            clinic_id=clinic.id,
            clinic_name=clinic.name,
            filepath=filepath,
            filename=os.path.basename(filepath),
            file_format=detection.format,
            detected_table=None,
            detection_confidence=0.0,
            suggested_clinic_name=detection.suggested_clinic_name,
            status="error",
        )
        return store.save_session(session)

    resolved_table = target_table or detection.detected_table

    # Run column matching engine
    raw_mapping = match_columns(
        source_headers=list(detection.dataframe.columns),
        target_table=resolved_table or "",
        use_ai=use_ai,
        models_dir=models_dir,
    )

    # Convert matcher result to domain entities
    def _to_domain(m) -> ColumnMatch:
        return ColumnMatch(
            source=m.source,
            target=m.target,
            method=m.method,
            confidence=m.confidence,
            description=m.description,
        )

    session = MappingSession(
        session_id=uuid.uuid4().hex,
        clinic_id=clinic.id,
        clinic_name=clinic.name,
        filepath=filepath,
        filename=os.path.basename(filepath),
        file_format=detection.format,
        detected_table=resolved_table,
        detection_confidence=detection.confidence,
        suggested_clinic_name=detection.suggested_clinic_name,
        auto_matched=[_to_domain(m) for m in raw_mapping.auto_matched],
        ai_suggestions=[_to_domain(m) for m in raw_mapping.ai_suggestions],
        unmatched=[_to_domain(m) for m in raw_mapping.unmatched],
        dataframe=detection.dataframe,
        status="pending_review" if resolved_table else "error",
    )

    return store.save_session(session)


def apply_user_decisions(
    session: MappingSession,
    user_decisions: Dict[str, Optional[str]],
) -> MappingSession:
    """
    Apply the user's column accept/reject decisions and load data into staging.
    """
    if session.dataframe is None:
        session.status = "error"
        return store.save_session(session)

    df = session.dataframe.copy()

    # Build final column map: source -> target
    col_map: Dict[str, str] = {}

    # Auto-matched are always applied
    for m in session.auto_matched:
        if m.target:
            col_map[m.source] = m.target

    # AI suggestions: apply user decisions
    for m in session.ai_suggestions:
        decision = user_decisions.get(m.source)
        if decision:
            col_map[m.source] = decision

    # User can also manually resolve unmatched columns
    for m in session.unmatched:
        decision = user_decisions.get(m.source)
        if decision:
            col_map[m.source] = decision

    # Rename columns and apply basic CLEANING
    from infrastructure.mapping_engine.cleaners import (
        clean_icd_code, clean_english_text, clean_ward, 
        clean_los, format_date_swiss, extract_numeric_id,
        generate_synthetic_case_id
    )

    mapped_df = pd.DataFrame()
    for src, tgt in col_map.items():
        if src in df.columns:
            series = df[src]
            
            # Apply specific cleaners based on target column name
            if tgt in ("coPrimary_icd10_code", "coSecondary_icd10_codes", "coOps_codes"):
                series = series.apply(clean_icd_code)
            elif tgt == "coWard":
                series = series.apply(clean_ward)
            elif tgt == "coLength_of_stay_days":
                series = series.apply(clean_los)
            elif tgt in ("coAdmission_date", "coDischarge_date"):
                series = series.apply(format_date_swiss)
            elif tgt in ("coCaseId", "coPatientId"):
                series = series.apply(extract_numeric_id)
            else:
                # Default for other columns (text cleanup)
                series = series.apply(clean_english_text)
                
            mapped_df[tgt] = series

    # Handle Synthetic CaseID Rule: Missing CaseID + Existing PatientID
    if "coCaseId" in mapped_df.columns and "coPatientId" in mapped_df.columns:
        mask = mapped_df["coCaseId"].isna() & mapped_df["coPatientId"].notna()
        if mask.any():
            mapped_df.loc[mask, "coCaseId"] = mapped_df.loc[mask, "coPatientId"].apply(generate_synthetic_case_id)

    # Fill remaining schema columns with None
    schema = STAGING_SCHEMAS.get(session.detected_table, {})
    for col in schema.get("columns", []):
        if col != "coId" and col not in mapped_df.columns:
            mapped_df[col] = None

    # Cast IDs to Int64 to avoid float conversion of NaNs
    for id_col in ["coCaseId", "coPatientId", "coClinicId"]:
        if id_col in mapped_df.columns:
            mapped_df[id_col] = pd.to_numeric(mapped_df[id_col], errors="coerce").astype("Int64")

    session.mapped_df = mapped_df

    # Validate
    raw_issues = validate_dataframe(mapped_df, session.detected_table)
    session.quality_issues = [
        QualityIssue(
            entity_name=q.entity_name,
            field_name=q.field_name,
            record_key=q.record_key,
            rule_name=q.rule_name,
            old_value=q.old_value,
            new_value=q.new_value,
            severity=q.severity,
            check_type=q.check_type,
            description=q.description,
        )
        for q in raw_issues
    ]

    # Load into staging
    rows = store.append_to_staging(session.detected_table, mapped_df)
    session.rows_loaded = rows
    session.status = "loaded"

    return store.save_session(session)


def edit_column_mapping(
    session: MappingSession,
    source: str,
    new_target: Optional[str],
) -> bool:
    """Manually override a single column mapping in a pending session."""
    if session.status == "loaded":
        return False

    for col_list in [session.auto_matched, session.ai_suggestions, session.unmatched]:
        for m in col_list:
            if m.source == source:
                old_target = m.target
                m.target = new_target
                m.method = "user"
                m.description = f"Manually set by user: {old_target} -> {new_target}"
                # If it was unmatched and now has a target, promote it
                if col_list is session.unmatched and new_target:
                    session.unmatched.remove(m)
                    session.auto_matched.append(m)
                store.save_session(session)
                return True

    return False


def get_session_stats(session: MappingSession) -> Dict[str, Any]:
    """
    Generate statistics for the interactive dashboard.
    """
    total_cols = len(session.auto_matched) + len(session.ai_suggestions) + len(session.unmatched)
    mapped_cols = len([m for m in session.auto_matched if m.target]) + \
                  len([m for m in session.ai_suggestions if m.target])
    
    mapping_score = (mapped_cols / total_cols * 100) if total_cols > 0 else 0
    
    # Quality Issues breakdown
    issues_by_severity = {"ERROR": 0, "WARNING": 0, "INFO": 0}
    for issue in session.quality_issues:
        issues_by_severity[issue.severity] = issues_by_severity.get(issue.severity, 0) + 1
        
    # Completeness (non-null rows in critical columns)
    completeness = 0.0
    if session.mapped_df is not None and not session.mapped_df.empty:
        # Simple heuristic: % of non-null values across the whole df
        completeness = (session.mapped_df.notna().sum().sum() / 
                       (session.mapped_df.shape[0] * session.mapped_df.shape[1]) * 100)
    
    return {
        "session_id": session.session_id,
        "filename": session.filename,
        "status": session.status,
        "metrics": {
            "mapping_confidence_avg": session.detection_confidence * 100,
            "mapping_completeness_pct": mapping_score,
            "data_completeness_pct": completeness,
            "total_rows": len(session.mapped_df) if session.mapped_df is not None else 0
        },
        "quality_summary": {
            "total_issues": len(session.quality_issues),
            "by_severity": issues_by_severity
        },
        "is_unstructured": session.file_format == "pdf" or "report" in session.filename.lower()
    }
