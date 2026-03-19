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
    get_session_stats,
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


class SessionOut(BaseModel):
    session_id: str
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

def _session_to_out(session) -> SessionOut:
    total = len(session.dataframe) if session.dataframe is not None else 0
    return SessionOut(
        session_id=session.session_id,
        clinic_id=session.clinic_id,
        clinic_name=session.clinic_name,
        filename=session.filename,
        detected_table=session.detected_table,
        detection_confidence=round(session.detection_confidence, 3),
        suggested_clinic_name=session.suggested_clinic_name,
        auto_matched=[ColumnMatchOut(**m.__dict__) for m in session.auto_matched],
        ai_suggestions=[ColumnMatchOut(**m.__dict__) for m in session.ai_suggestions],
        unmatched=[ColumnMatchOut(**m.__dict__) for m in session.unmatched],
        total_rows=total,
        status=session.status,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload/{clinic_id}", response_model=SessionOut)
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

    Then call POST /mapping/approve/{session_id} with the user's decisions.
    """
    clinic = get_clinic(clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail=f"Clinic {clinic_id} not found")

    ext = os.path.splitext(file.filename)[1]
    temp_path = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}{ext}")
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    session = process_upload(
        filepath=temp_path,
        clinic=clinic,
        target_table=target_table,
        use_ai=use_ai,
    )

    if session.status == "error":
        raise HTTPException(
            status_code=422,
            detail="Could not identify this file's type. Specify target_table manually.",
        )

    return _session_to_out(session)


@router.get("/session/{session_id}", response_model=SessionOut)
def get_session(session_id: str):
    """Get the current state of a mapping session."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_out(session)


@router.post("/approve/{session_id}")
def approve_mapping(session_id: str, body: ApproveRequest):
    """
    Submit user decisions for AI suggestions and unmatched columns, then load data.

    - `accepted_target` = "coAdmissionDate" → map the column
    - `accepted_target` = null              → reject (field stays NULL)

    Auto-matched columns are always included automatically.
    """
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "loaded":
        raise HTTPException(status_code=400, detail="Session already loaded")

    decisions = {d.source: d.accepted_target for d in body.decisions}
    session = apply_user_decisions(session, decisions)

    return {
        "session_id": session_id,
        "status": session.status,
        "target_table": session.detected_table,
        "rows_loaded": session.rows_loaded,
        "quality_issues_count": len(session.quality_issues),
        "quality_issues": [
            {
                "field": q.field_name,
                "rule": q.rule_name,
                "severity": q.severity,
                "description": q.description,
            }
            for q in session.quality_issues
        ],
    }


@router.put("/session/{session_id}/column")
def update_column(
    session_id: str,
    source: str = Query(...),
    new_target: Optional[str] = Query(None),
):
    """
    Edit a single column mapping in a pending session.
    Set new_target=null to unmap a column.
    """
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "loaded":
        raise HTTPException(status_code=400, detail="Session already loaded, cannot edit")

    updated = edit_column_mapping(session, source, new_target)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Column '{source}' not found in session")

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


@router.get("/quality/{session_id}")
def get_quality_issues(session_id: str):
    """Get quality issues detected after loading a session."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
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
        for q in session.quality_issues
    ]

@router.get("/session/{session_id}/stats")
def get_stats(session_id: str):
    """
    Get dashboard metrics for a specific mapping session.
    Includes mapping completeness, data quality summary, and row counts.
    """
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return get_session_stats(session)
