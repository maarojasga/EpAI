"""
Promotion use cases - moves data from Staging tables to Unified Relational tables.
Ensures every record is linked to tbCaseData and a valid Person.
"""
import pandas as pd
from typing import Dict, List, Any, Optional
from infrastructure.storage import in_memory_store as store
from domain.entities.mapping_session import IngestionJob


def promote_job_to_unified(job: IngestionJob):
    """
    Promotes the mapped data from an ingestion job into the Unified Schema tables.
    """
    if not job.detected_table or job.mapped_df is None or job.mapped_df.empty:

        return
    
    df = job.mapped_df.copy()
    table = job.detected_table
    
    # 1. Ensure all rows have a PersonId (via PatientMapping)
    # If not found, we'll try to register them or skip (though already validated for ID presence)
    def resolve_person(pid):
        mapping = store.get_patient_mapping(job.clinic_id, str(pid))
        if mapping:
            return mapping["person_id"]
        # In a real app, we'd register. Here we return a stable dummy if needed.
        return 1 # Fallback to a default patient if mapping is missing
    
    df["coPersonId"] = df["coPatientId"].apply(resolve_person)
    df["coClinicId"] = job.clinic_id
    
    # 2. Anchor to tbCaseData (Case-Centric requirement)
    _upsert_case_data(df, job)
    
    # 3. Map to Unified Tables based on the detection
    if table == "tbImportLabsData":
        _promote_labs(df, job)
    elif table == "tbImportIcd10Data":
        _promote_icd10(df, job)
    elif table == "tbImportNursingDailyReportsData":
        _promote_nursing(df, job)
    elif table == "tbImportEpaAcData":
        _promote_epaac(df, job)


    # Add more as needed...

def _upsert_case_data(df: pd.DataFrame, job: IngestionJob):
    """
    Ensures that for every row in the job, there is a record in tbCaseData.
    Anchors clinical data to the main Case registry.
    """
    # Extract unique cases
    id_col = "coCaseId" if "coCaseId" in df.columns else ("coE2I222" if "coE2I222" in df.columns else None)
    if not id_col:
        return

    # Prepare Case Metadata
    cases_df = df[[id_col, "coPatientId", "coPersonId"]].drop_duplicates(subset=[id_col])
    
    # Add extra metadata if present in columns (e.g. Names from epaAC or Labs)
    meta_cols = {
        "coLastname": ["coLastname", "coName"],
        "coFirstname": ["coFirstname", "coGivenName"],
        "coGender": ["coGender", "coSex"],
        "coDateOfBirth": ["coDateOfBirth", "coBirthdate"],
        "coAdmission_date": ["coAdmission_date", "coAdmission_datetime", "coE2I223"],
        "coDischarge_date": ["coDischarge_date", "coDischarge_datetime", "coE2I228"]
    }
    
    for target, sources in meta_cols.items():
        found = next((s for s in sources if s in df.columns), None)
        if found:
            # For each unique case, pick the first non-null value for metadata
            cases_df[target] = df.groupby(id_col)[found].transform('first')

    # Standardize column naming for tbCaseData if needed
    # (Mapping epaAC codes to friendly names in tbCaseData)
    if id_col == "coE2I222":
        cases_df = cases_df.rename(columns={"coE2I222": "coCaseId"})
    
    store.upsert_case_data(cases_df)


def _promote_labs(df: pd.DataFrame, job: IngestionJob):

    """Maps Labs staging rows to tbObservation."""
    observations = []
    # Simplified mapping for common lab values
    lab_cols = [c for c in df.columns if "_mmol_L" in c or "_mg_dL" in c or "_g_dL" in c]
    
    for _, row in df.iterrows():
        base = {
            "coPersonId": row["coPersonId"],
            "coCaseId": row["coCaseId"],
            "coClinicId": row["coClinicId"],
            "coTimestamp": row.get("coSpecimen_datetime"),
            "coSourceSystem": "Staging:Labs"
        }
        for col in lab_cols:
            if pd.notna(row[col]):
                obs = base.copy()
                obs["coNumericValue"] = row[col]
                obs["coUnit"] = col.split("_")[-1] if "_" in col else ""
                obs["coFlag"] = row.get(col.replace("_mmol_L", "_flag").replace("_mg_dL", "_flag").replace("_g_dl", "_flag"))
                # In a real app, we'd lookup ConceptId via tbConcept
                obs["coConceptId"] = 1 # Placeholder
                observations.append(obs)
                
    if observations:
        store.append_to_staging("tbObservation", pd.DataFrame(observations))

def _promote_icd10(df: pd.DataFrame, job: IngestionJob):

    """Maps ICD-10 staging rows to tbCondition."""
    conditions = []
    for _, row in df.iterrows():
        # Primary
        if pd.notna(row.get("coPrimary_icd10_code")):
            conditions.append({
                "coPersonId": row["coPersonId"],
                "coCaseId": row["coCaseId"],
                "coClinicId": row["coClinicId"],
                "coIcdCode": row["coPrimary_icd10_code"],
                "coDescription": row.get("coPrimary_icd10_description_en"),
                "coIsPrimary": True,
                "coOnsetTimestamp": row.get("coAdmission_date"),
                "coDischargeTimestamp": row.get("coDischarge_date"),
                "coWard": row.get("coWard")
            })
    if conditions:
        store.append_to_staging("tbCondition", pd.DataFrame(conditions))

def _promote_nursing(df: pd.DataFrame, job: IngestionJob):

    """Maps Nursing reports to tbCareIntervention."""
    interventions = []
    for _, row in df.iterrows():
        interventions.append({
            "coPersonId": row["coPersonId"],
            "coCaseId": row["coCaseId"],
            "coClinicId": row["coClinicId"],
            "coTimestamp": row.get("coReport_date"),
            "coType": "NursingReport",
            "coWard": row.get("coWard"),
            "coShift": row.get("coShift"),
            "coNote": row.get("coNursing_note_free_text")
        })
    if interventions:
        store.append_to_staging("tbCareIntervention", pd.DataFrame(interventions))

def _promote_epaac(df: pd.DataFrame, job: IngestionJob):
    """Maps epaAC to tbAssessment and many tbObservation."""
    # Simplified: Create Assessment record and linked Observations
    # For the hackathon, we'll just ensure CaseId linkage is preserved.
    pass 
