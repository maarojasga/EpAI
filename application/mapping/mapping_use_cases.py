import os
import uuid
from typing import Any, Dict, List, Optional
import numpy as np

import pandas as pd
import logging

logger = logging.getLogger(__name__)

from domain.entities.clinic import Clinic

from domain.entities.mapping_session import IngestionJob, ColumnMatch

from domain.entities.quality_issue import QualityIssue
from application.mapping import promotion_use_cases
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
) -> IngestionJob:
    """
    Detect the file format, match columns, and persist a pending job.
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
        job = IngestionJob(
            job_id=uuid.uuid4().hex,
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
        return store.save_ingestion_job(job)


    resolved_table = target_table or detection.detected_table

    source_headers = list(detection.dataframe.columns)

    # Extract samples for AI inference (first 5 rows for each column)
    samples = {col: detection.dataframe[col].dropna().head(5).tolist() for col in source_headers}

    # If target_table is not provided, try to auto-detect it using samples
    if not resolved_table:
        # This part assumes 'detect' function can take samples for table detection,
        # but the current 'detect' function only takes filepath.
        # For now, we'll use the original detection.detected_table if target_table is None.
        # If the intention was to re-run table detection with samples, the 'detect' function
        # would need to be updated or a new 'detect_table' function created.
        # For this edit, we'll stick to the existing 'resolved_table' logic.
        pass # No change needed here based on the provided snippet, as resolved_table is already set.

    # Run column matching engine
    raw_mapping = match_columns(
        source_headers=source_headers,
        target_table=resolved_table or "",
        use_ai=use_ai,
        models_dir=models_dir,
        samples=samples, # Pass samples to match_columns
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

    job = IngestionJob(
        job_id=uuid.uuid4().hex,
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
        normalization_audit={},
    )

    # AUTO-ACCEPT LOGIC (96% threshold)
    if job.status == "pending_review" and job.detection_confidence >= 0.96:
        logger.info(f"Auto-accepting file: {job.filename} (Confidence: {job.detection_confidence})")
        # For auto-accept, decisions is an empty dict because all are auto-matched or ai-suggestions
        # are handled differently if we want to auto-map EVERYTHING.
        # But wait, raw_mapping already has auto_matched. 
        # Actually, we just call it with an empty dict to Trigger the load logic.
        return apply_user_decisions(job, {})


    return store.save_ingestion_job(job)



def apply_user_decisions(
    job: IngestionJob,
    user_decisions: Dict[str, Optional[str]],
) -> IngestionJob:
    """
    Apply the user's column accept/reject decisions and load data into staging.
    """
    if job.dataframe is None:
        job.status = "error"
        return store.save_ingestion_job(job)

    df = job.dataframe.copy()


    # Build final column map: source -> target
    col_map: Dict[str, str] = {}

    # Auto-matched are always applied
    for m in job.auto_matched:
        if m.target:
            col_map[m.source] = m.target

    # AI suggestions: apply user decisions
    for m in job.ai_suggestions:
        decision = user_decisions.get(m.source)
        if decision:
            col_map[m.source] = decision

    # User can also manually resolve unmatched columns
    for m in job.unmatched:
        decision = user_decisions.get(m.source)
        if decision:
            col_map[m.source] = decision


    # Rename columns and apply basic CLEANING
    from infrastructure.mapping_engine.cleaners import (
        clean_icd_code, clean_ward, 
        format_date_swiss, extract_numeric_id,
        generate_synthetic_case_id, clean_sex,
        clean_lab_flag, clean_numeric,
        clean_record_type, clean_order_status, clean_admin_status,
        clean_route, clean_prn, clean_epaac_val
    )

    from infrastructure.mapping_engine.validators import QualityIssue as DomainQualityIssue

    cleaning_audits: List[DomainQualityIssue] = []

    def _audit_clean(series: pd.Series, cleaner_func, rule_name: str, justification: str, target_col: str):
        """Helper to apply cleaner and log any changes for human review."""
        original = series.copy()
        cleaned = series.apply(cleaner_func)
        
        # 1. Update normalization_audit for the Dashboard (Before vs After)
        # Identify unique transformations for this column
        diff_mask = (original.astype(str) != cleaned.astype(str)) & cleaned.notna()
        if diff_mask.any():
            if target_col not in job.normalization_audit:
                job.normalization_audit[target_col] = []
            
            # Extract samples (unique pairs of old -> new)
            samples_df = pd.DataFrame({"old": original[diff_mask], "new": cleaned[diff_mask]})
            samples = samples_df.drop_duplicates().head(50).to_dict("records")
            
            # Avoid duplicate entries in the audit list
            existing = {(s["old"], s["new"]) for s in job.normalization_audit[target_col]}
            for s in samples:
                if (s["old"], s["new"]) not in existing:
                    job.normalization_audit[target_col].append(s)

        # 2. Update quality_issues (individual record-level alerts)
        mask = (original.notna() & (original.astype(str) != cleaned.astype(str)))
        changed_indices = original[mask].index[:10] # Log up to 10 samples per column to avoid bloat
        
        for idx in changed_indices:
            cleaning_audits.append(DomainQualityIssue(
                entity_name=job.detected_table or "unknown",
                field_name=target_col,
                record_key=f"Row {idx}",
                rule_name=rule_name,
                old_value=str(original[idx]),
                new_value=str(cleaned[idx]),
                severity="CLEANED",
                check_type="cleaning_audit",
                description=justification
            ))
        return cleaned



    mapped_df = pd.DataFrame()
    for src, tgt in col_map.items():
        if src in df.columns:
            series = df[src]
            tgt_lower = tgt.lower()
            
            # Apply specific cleaners with Audit
            if tgt in ("coPrimary_icd10_code", "coSecondary_icd10_codes", "coOps_codes"):
                series = _audit_clean(series, clean_icd_code, "ICD_NORMALIZATION", "Formatted code and removed trailing special characters.", tgt)
            elif tgt == "coWard":
                series = _audit_clean(series, clean_ward, "WARD_STANDARDIZATION", "Mapped to canonical German department name.", tgt)
            elif tgt in ("coAdmission_date", "coDischarge_date", "coAdmission_datetime", "coDischarge_datetime", "coSpecimen_datetime"):
                series = _audit_clean(series, format_date_swiss, "DATE_NORMALIZATION", "Converted to Swiss standard format (DD.MM.YYYY).", tgt)
            elif tgt in ("coCaseId", "coPatientId", "coPatientId", "coClinicId", "coE2I222") or "patientid" in tgt_lower or "caseid" in tgt_lower:
                series = _audit_clean(series, extract_numeric_id, "STRICT_ID_NORMALIZATION", "Removed all letters, hyphens, and non-numeric characters to extract a clean Integer ID.", tgt)



            elif "sex" in tgt_lower or "gender" in tgt_lower:
                series = _audit_clean(series, clean_sex, "SEX_MAPPING", "Standardized bilingual sex/gender strings to M/F.", tgt)
            elif tgt_lower.endswith("_flag"):
                series = _audit_clean(series, clean_lab_flag, "FLAG_NORMALIZATION", "Verified and cleaned clinical flag (H, L, HH, LL).", tgt)
            elif tgt == "coRecord_type":
                series = _audit_clean(series, clean_record_type, "RECORD_TYPE_STANDARDIZATION", "Normalized to ORDER/ADMIN/CHANGE.", tgt)
            elif tgt == "order_status":
                series = _audit_clean(series, clean_order_status, "ORDER_STATUS_STANDARDIZATION", "Normalized medical order status.", tgt)
            elif tgt == "administration_status":
                series = _audit_clean(series, clean_admin_status, "ADMIN_STATUS_STANDARDIZATION", "Normalized administration status.", tgt)
            elif tgt == "coRoute":
                series = _audit_clean(series, clean_route, "ROUTE_NORMALIZATION", "Formatted administration route to standard acronym.", tgt)
            elif tgt == "coIs_prn_0_1":
                series = _audit_clean(series, clean_prn, "PRN_BOOLEAN_MAPPING", "Resolved PRN strings/booleans to binary 0/1.", tgt)
            elif any(u in tgt_lower for u in ["_mmol_l", "_mg_dl", "_g_dl", "_10e9_l", "_u_l", "age_years", "score", "magnitude", "dose"]):
                series = _audit_clean(series, clean_numeric, "NUMERIC_CLEANING", "Sanitized numeric value and handled units/anomalies.", tgt)
            elif tgt.startswith(("coE0I", "coE1I", "coE2I", "coE3I")):
                # epaAC Variables - Resolve SID to Name
                catalog = os.getenv("CATALOG_PATH", "data/IID-SID-ITEM.csv")

                series = _audit_clean(series, lambda x: clean_epaac_val(x, catalog), "SID_RESOLUTION", "Resolved internal SID code to human-readable assessment item name.", tgt)

            
            mapped_df[tgt] = series

    # Handle Synthetic CaseID Rule: Missing CaseID + Existing PatientID
    # We apply this to both coCaseId and coE2I222 (used in tbCaseData)
    for cid_col in ["coCaseId", "coE2I222"]:
        if cid_col in mapped_df.columns and "coPatientId" in mapped_df.columns:
            mask = mapped_df[cid_col].isna() & mapped_df["coPatientId"].notna()
            if mask.any():
                mapped_df.loc[mask, cid_col] = mapped_df.loc[mask, "coPatientId"].apply(generate_synthetic_case_id)


    # SMART DEDUPLICATION AND STRICT DATA INTEGRITY
    # 1. Identify records missing CaseID or PatientID
    required_cols = []
    if "coCaseId" in mapped_df.columns: required_cols.append("coCaseId")
    if "coPatientId" in mapped_df.columns: required_cols.append("coPatientId")
    if "coE2I222" in mapped_df.columns: required_cols.append("coE2I222")

    invalid_mask = pd.Series(False, index=mapped_df.index)
    for col in required_cols:
        invalid_mask |= mapped_df[col].isna()
    
    if invalid_mask.any():
        for idx in mapped_df[invalid_mask].index:
            job.rejected_rows.append({
                "row": int(idx),
                "reason": "Missing Mandatory ID (Case/Patient)",
                "data": mapped_df.loc[idx].replace({np.nan: None}).to_dict()
            })
        mapped_df = mapped_df[~invalid_mask]


    # 1.5 Convert all empty or whitespace-only strings to genuine Nulls
    mapped_df = mapped_df.replace(r'^\s*$', np.nan, regex=True)
        
    # 2. Prevent Duplicates (Deduplicate against current job and existing staging table)
    # 2a. Deduplicate within current batch/file first and log
    initial_count = len(mapped_df)
    
    # "The last record is authoritative for duplicates" (epaAC-Data-1 requirement)
    # Most tables keep first (original behavior), but epaAC specifically needs 'last'.
    dedup_strategy = 'last' if job.detected_table == "tbImportEpaAcData" else 'first'
    unique_mask = ~mapped_df.duplicated(keep=dedup_strategy)

    
    if (~unique_mask).any():
        for idx in mapped_df[~unique_mask].index:
            job.rejected_rows.append({
                "row": int(idx),
                "reason": "Duplicate Record (Identical row found within the same file)",
                "data": mapped_df.loc[idx].replace({np.nan: None}).to_dict()
            })
        mapped_df = mapped_df[unique_mask]

    
    # Deduplicate against existing staging table in DB
    existing_df = store.get_staging_table(job.detected_table) if job.detected_table else None

    
    if existing_df is not None and not existing_df.empty and not mapped_df.empty:
        # Resolve common columns for comparison
        cols_to_compare = [c for c in mapped_df.columns if c in existing_df.columns and c != "coId"]
        if cols_to_compare:
            # We use a set of tuples for fast lookup of existing records
            existing_records = set(existing_df[cols_to_compare].fillna("NULL").astype(str).apply(tuple, axis=1))
            
            # Identify which rows in mapped_df already exist
            current_records = mapped_df[cols_to_compare].fillna("NULL").astype(str).apply(tuple, axis=1)
            dupe_mask = current_records.isin(existing_records)
            
            if dupe_mask.any():
                for idx in mapped_df[dupe_mask].index:
                    job.rejected_rows.append({
                        "row": int(idx),
                        "reason": "Duplicate Record (Already exists in staging database)",
                        "data": mapped_df.loc[idx].replace({np.nan: None}).to_dict()
                    })
                mapped_df = mapped_df[~dupe_mask]

    # 3. Labs-specific deduplication (Keep most complete specimen)
    if job.detected_table == "tbImportLabsData" and "coCaseId" in mapped_df.columns and "coSpecimen_datetime" in mapped_df.columns:

        mapped_df["_completeness"] = mapped_df.notna().sum(axis=1)
        mapped_df = mapped_df.sort_values(by=["coCaseId", "coSpecimen_datetime", "_completeness"], ascending=[True, True, False])
        mapped_df = mapped_df.drop_duplicates(subset=["coCaseId", "coSpecimen_datetime"], keep="first")
        mapped_df = mapped_df.drop(columns=["_completeness"])


    # Cast IDs to Int64 to avoid float conversion of NaNs
    for col in required_cols:
        if col in mapped_df.columns:
            mapped_df[col] = mapped_df[col].astype('Int64')

    job.mapped_df = mapped_df
    
    # 4. Final Load Count & PERSISTENCE
    job.rows_loaded = store.append_to_staging(job.detected_table, mapped_df) if job.detected_table else 0
    logger.info(f"Loaded {job.rows_loaded} rows into {job.detected_table}. Rejected: {len(job.rejected_rows)}")

    # 5. RELATIONAL PROMOTION: Move to tbObservation, tbCondition, etc.
    if job.rows_loaded > 0:
        try:
            logger.info("Starting relational promotion to unified schema...")
            promotion_use_cases.promote_job_to_unified(job)
            logger.info("Relational promotion completed successfully.")
        except Exception as e:
            logger.error(f"Promotion error: {e}")



    job.status = "loaded"
    return store.save_ingestion_job(job)





def edit_column_mapping(
    job: IngestionJob,
    source: str,
    new_target: Optional[str],
) -> bool:
    """Manually override a single column mapping in a pending job."""
    if job.status == "loaded":
        return False

    for col_list in [job.auto_matched, job.ai_suggestions, job.unmatched]:

        for m in col_list:
            if m.source == source:
                old_target = m.target
                m.target = new_target
                m.method = "user"
                m.description = f"Manually set by user: {old_target} -> {new_target}"
                # If it was unmatched and now has a target, promote it
                if col_list is job.unmatched and new_target:
                    job.unmatched.remove(m)
                    job.auto_matched.append(m)
                store.save_ingestion_job(job)
                return True

    return False



def get_ingestion_job_stats(job: IngestionJob) -> Dict[str, Any]:
    """
    Generate statistics for the ingestion job view.
    """

    total_cols = len(job.auto_matched) + len(job.ai_suggestions) + len(job.unmatched)
    mapped_cols = len([m for m in job.auto_matched if m.target]) + \
                  len([m for m in job.ai_suggestions if m.target])
    
    mapping_score = (mapped_cols / total_cols * 100) if total_cols > 0 else 0
    
    # Quality Issues breakdown
    issues_by_severity = {"ERROR": 0, "WARNING": 0, "INFO": 0, "CLEANED": 0}
    for issue in job.quality_issues:
        issues_by_severity[issue.severity] = issues_by_severity.get(issue.severity, 0) + 1
        
    # Completeness (non-null rows in critical columns)
    completeness = 0.0
    if job.mapped_df is not None and not job.mapped_df.empty:
        # Simple heuristic: % of non-null values across the whole df
        completeness = (job.mapped_df.notna().sum().sum() / 
                       (job.mapped_df.shape[0] * job.mapped_df.shape[1]) * 100)
    
    return {
        "job_id": job.job_id,
        "filename": job.filename,
        "status": job.status,
        "table": job.detected_table,
        "metrics": {
            "mapping_confidence_avg": job.detection_confidence * 100,
            "mapping_completeness_pct": mapping_score,
            "data_completeness_pct": completeness,
            "total_rows_loaded": job.rows_loaded,
            "total_rejected": len(job.rejected_rows)
        },
        "quality_summary": {
            "total_issues": len(job.quality_issues),
            "by_severity": issues_by_severity
        },
        "is_unstructured": job.file_format == "pdf" or "report" in job.filename.lower()
    }

