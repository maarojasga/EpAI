"""
api/v1/mapping.py - Mapping pipeline endpoints.
"""
import os
import shutil
import tempfile
import uuid
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from application.clinics.clinic_use_cases import get_clinic
from application.mapping.mapping_use_cases import (
    process_upload,
    apply_user_decisions,
    edit_column_mapping,
    get_ingestion_job_stats,
)
from infrastructure.storage import in_memory_store as store

from infrastructure.mapping_engine.profiles import STAGING_SCHEMAS

router = APIRouter(prefix="/mapping", tags=["Mapping"])

TEMP_DIR = tempfile.mkdtemp(prefix="epai_upload_")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ColumnMatchOut(BaseModel):
    source: str
    target: Optional[str]
    method: str
    confidence: float
    description: str


class IngestionJobOut(BaseModel):
    job_id: str
    clinic_id: int
    clinic_name: str
    filename: str
    detected_table: Optional[str]
    detection_confidence: float
    suggested_clinic_name: Optional[str]
    auto_matched: List[ColumnMatchOut]
    ai_suggestions: List[ColumnMatchOut]
    unmatched: List[ColumnMatchOut]
    total_rows: int
    status: str



class ColumnDecision(BaseModel):
    source: str
    accepted_target: Optional[str] = None


class ApproveRequest(BaseModel):
    decisions: List[ColumnDecision]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job_to_out(job) -> IngestionJobOut:
    total = len(job.dataframe) if job.dataframe is not None else 0
    return IngestionJobOut(
        job_id=job.job_id,
        clinic_id=job.clinic_id,
        clinic_name=job.clinic_name,
        filename=job.filename,
        detected_table=job.detected_table,
        detection_confidence=round(job.detection_confidence, 3),
        suggested_clinic_name=job.suggested_clinic_name,
        auto_matched=[ColumnMatchOut(**m.__dict__) for m in job.auto_matched],
        ai_suggestions=[ColumnMatchOut(**m.__dict__) for m in job.ai_suggestions],
        unmatched=[ColumnMatchOut(**m.__dict__) for m in job.unmatched],
        total_rows=total,
        status=job.status,
    )



# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload/{clinic_id}", response_model=IngestionJobOut)

async def upload_file(
    clinic_id: int,
    file: UploadFile = File(...),
    target_table: Optional[str] = Query(None),
    use_ai: bool = Query(True),
):
    """
    Upload a file for a clinic and get mapping suggestions.

    Response contains three lists for the front-end:
    - `auto_matched`   → ✅ show in green (auto-confirmed)
    - `ai_suggestions` → 🟡 show in yellow (need user accept/reject)
    - `unmatched`      → 🔴 show in red (user must map manually or leave NULL)

    Then call POST /mapping/approve/{job_id} with the user's decisions.
    """

    clinic = get_clinic(clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail=f"Clinic {clinic_id} not found")

    ext = os.path.splitext(file.filename)[1]
    temp_path = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}{ext}")
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    job = process_upload(
        filepath=temp_path,
        clinic=clinic,
        target_table=target_table,
        use_ai=use_ai,
    )

    if job.status == "error":

        raise HTTPException(
            status_code=422,
            detail="Could not identify this file's type. Specify target_table manually.",
        )

    return _job_to_out(job)



@router.get("/session/{job_id}", response_model=IngestionJobOut)
def get_ingestion_job(job_id: str):

    """Get the current state of an ingestion job."""
    job = store.get_ingestion_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return _job_to_out(job)



@router.post("/approve/{job_id}")
def approve_mapping(job_id: str, body: ApproveRequest):
    """
    Submit user decisions for AI suggestions and unmatched columns, then load data.
    """
    job = store.get_ingestion_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    if job.status == "loaded":
        raise HTTPException(status_code=400, detail="Job already loaded")

    decisions = {d.source: d.accepted_target for d in body.decisions}
    job = apply_user_decisions(job, decisions)

    return {
        "job_id": job_id,
        "status": job.status,
        "target_table": job.detected_table,
        "rows_loaded": job.rows_loaded,
        "quality_issues_count": len(job.quality_issues),
        "quality_issues": [
            {
                "field": q.field_name,
                "rule": q.rule_name,
                "severity": q.severity,
                "description": q.description,
            }
            for q in job.quality_issues
        ],
    }



@router.put("/session/{job_id}/column")
def update_column(
    job_id: str,

    source: str = Query(...),
    new_target: Optional[str] = Query(None),
):
    """
    Edit a single column mapping in a pending ingestion job.
    """
    job = store.get_ingestion_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    if job.status == "loaded":
        raise HTTPException(status_code=400, detail="Job already loaded, cannot edit")

    updated = edit_column_mapping(job, source, new_target)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Column '{source}' not found in job")

    return {"updated": True, "source": source, "new_target": new_target}



@router.get("/tables")
def list_tables():
    """List all available staging table names."""
    return {"tables": list(STAGING_SCHEMAS.keys())}


@router.get("/available-columns/{table_name}")
def get_available_columns(table_name: str):
    """
    Return all mapable columns for a staging table.
    Used by the front-end to populate dropdown selectors.
    """
    schema = STAGING_SCHEMAS.get(table_name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return {
        "table": table_name,
        "columns": [c for c in schema["columns"] if c != "coId"],
    }



@router.get("/session/{job_id}/stats")
def get_job_stats_endpoint(job_id: str):
    """
    Get dashboard metrics for a specific ingestion job.
    """
    stats = get_ingestion_job_stats(job_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Job stats not found")
    return stats

@router.get("/session/{job_id}", response_model=IngestionJobOut)
def get_ingestion_job(job_id: str):
    """Get the current state of an ingestion job."""
    job = store.get_ingestion_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    
    # Map to output model
    return IngestionJobOut(
        job_id=job.job_id,
        filename=job.filename,
        status=job.status,
        table=job.detected_table,
        rows_loaded=job.rows_loaded,
        rejected_count=len(job.rejected_rows),
        normalization_audit=job.normalization_audit
    )


@router.get("/quality/{job_id}")
def get_quality_issues(job_id: str):
    """Get quality issues detected after loading an ingestion job."""
    job = store.get_ingestion_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return [
        {
            "entity_name": q.entity_name,
            "field_name": q.field_name,
            "record_key": q.record_key,
            "rule_name": q.rule_name,
            "old_value": q.old_value,
            "severity": q.severity,
            "description": q.description,
        }
        for q in job.quality_issues
    ]
