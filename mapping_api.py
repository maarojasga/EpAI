"""
mapping_api.py - FastAPI endpoints for the Smart Health Data Mapping pipeline.

Endpoints:
  GET  /clinics                      List all clinics
  POST /clinics                      Create a new clinic
  POST /mapping/upload/{clinic_id}   Upload file, get mapping suggestions
  GET  /mapping/session/{session_id} Get mapping session details
  POST /mapping/approve/{session_id} Submit user decisions and load data
  GET  /mapping/staging              Show staging table summaries
  GET  /mapping/quality/{session_id} Show quality issues for a session
"""

import os
import uuid
import shutil
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import our mapping pipeline
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mapping.pipeline import (
    process_file,
    apply_mapping,
    list_clinics,
    get_or_create_clinic,
    get_staging_summary,
    PipelineResult,
    STAGING_DB,
)
from mapping.matcher import ColumnMatch

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="EpAI Smart Health Data Mapping API",
    description="Auto-maps uploaded healthcare files to the Unified Smart Health Schema",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store: session_id -> PipelineResult
SESSIONS: Dict[str, PipelineResult] = {}
TEMP_DIR = tempfile.mkdtemp(prefix="epai_upload_")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ClinicCreate(BaseModel):
    name: str
    location: str = ""
    system_type: str = ""
    source_file_pattern: str = ""
    country: str = ""


class ClinicResponse(BaseModel):
    id: int
    name: str
    location: str
    system_type: str


class ColumnDecision(BaseModel):
    source: str
    accepted_target: Optional[str] = None  # None = reject (will be NULL)


class ApproveRequest(BaseModel):
    decisions: List[ColumnDecision]


class ColumnMatchResponse(BaseModel):
    source: str
    target: Optional[str]
    method: str
    confidence: float
    description: str


class MappingSessionResponse(BaseModel):
    session_id: str
    clinic_id: int
    clinic_name: str
    filename: str
    detected_table: Optional[str]
    detection_confidence: float
    auto_matched: List[ColumnMatchResponse]
    ai_suggestions: List[ColumnMatchResponse]
    unmatched: List[ColumnMatchResponse]
    total_rows: int
    status: str


class QualityIssueResponse(BaseModel):
    entity_name: str
    field_name: str
    record_key: str
    rule_name: str
    old_value: str
    severity: str
    description: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _match_to_response(m: ColumnMatch) -> ColumnMatchResponse:
    return ColumnMatchResponse(
        source=m.source,
        target=m.target,
        method=m.method,
        confidence=round(m.confidence, 3),
        description=m.description,
    )


def _session_to_response(session_id: str, result: PipelineResult) -> MappingSessionResponse:
    df = result.detection.dataframe
    total_rows = len(df) if df is not None else 0
    return MappingSessionResponse(
        session_id=session_id,
        clinic_id=result.clinic.get("id", 0),
        clinic_name=result.clinic.get("name", ""),
        filename=os.path.basename(result.detection.filepath),
        detected_table=result.detection.detected_table,
        detection_confidence=round(result.detection.confidence, 3),
        auto_matched=[_match_to_response(m) for m in result.mapping.auto_matched],
        ai_suggestions=[_match_to_response(m) for m in result.mapping.ai_suggestions],
        unmatched=[_match_to_response(m) for m in result.mapping.unmatched],
        total_rows=total_rows,
        status=result.status,
    )


# ---------------------------------------------------------------------------
# Clinic endpoints
# ---------------------------------------------------------------------------

@app.get("/clinics", response_model=List[ClinicResponse], tags=["Clinics"])
def get_clinics():
    """List all registered clinics."""
    return list_clinics()


@app.post("/clinics", response_model=ClinicResponse, tags=["Clinics"])
def create_clinic(body: ClinicCreate):
    """
    Register a new clinic (or return existing one if name already exists).
    """
    clinic = get_or_create_clinic(
        name=body.name,
        location=body.location,
        system_type=body.system_type,
    )
    return ClinicResponse(
        id=clinic["id"],
        name=clinic["name"],
        location=clinic.get("location", ""),
        system_type=clinic.get("system_type", ""),
    )


# ---------------------------------------------------------------------------
# Upload & mapping endpoints
# ---------------------------------------------------------------------------

@app.post("/mapping/upload/{clinic_id}", tags=["Mapping"])
async def upload_file(
    clinic_id: int,
    file: UploadFile = File(...),
    target_table: Optional[str] = Query(None, description="Force a specific staging table"),
    use_ai: bool = Query(True, description="Use AI for unmatched columns"),
):
    """
    Upload a file for a clinic. Returns mapping suggestions to review.

    The front-end should:
    1. Show auto_matched columns (green - confirmed)
    2. Show ai_suggestions (yellow - need user approval)
    3. Show unmatched columns (red - user can manually select target or leave NULL)

    Then call POST /mapping/approve/{session_id} with the decisions.
    """
    # Validate clinic exists
    clinics = list_clinics()
    clinic = next((c for c in clinics if c["id"] == clinic_id), None)
    if not clinic:
        raise HTTPException(status_code=404, detail=f"Clinic {clinic_id} not found")

    # Save uploaded file to temp dir
    ext = os.path.splitext(file.filename)[1]
    temp_path = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}{ext}")
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = process_file(
            filepath=temp_path,
            clinic_name=clinic["name"],
            clinic_location=clinic.get("location", ""),
            target_table=target_table,
            use_ai=use_ai,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

    if result.status == "error" or result.mapping.target_table == "unknown":
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not identify the table type for this file. "
                "Please specify target_table manually."
            ),
        )

    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = result

    return _session_to_response(session_id, result)


@app.get("/mapping/session/{session_id}", response_model=MappingSessionResponse, tags=["Mapping"])
def get_session(session_id: str):
    """Get the details of an existing mapping session."""
    result = SESSIONS.get(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_response(session_id, result)


@app.post("/mapping/approve/{session_id}", tags=["Mapping"])
def approve_mapping(session_id: str, body: ApproveRequest):
    """
    Submit user decisions for AI suggestions and unmatched columns.

    For each decision:
    - accepted_target = "coSodium_mmol_L"  => map source to this column
    - accepted_target = null               => reject, field will be NULL

    Auto-matched columns are always included automatically.
    Returns: rows loaded and quality issues found.
    """
    result = SESSIONS.get(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    if result.status == "loaded":
        raise HTTPException(status_code=400, detail="Session already loaded")

    # Build user_decisions dict
    user_decisions = {d.source: d.accepted_target for d in body.decisions}

    # Apply and load
    result = apply_mapping(result, user_decisions=user_decisions)
    SESSIONS[session_id] = result

    return {
        "session_id": session_id,
        "status": result.status,
        "target_table": result.mapping.target_table,
        "rows_loaded": result.rows_loaded,
        "quality_issues_count": len(result.quality_issues),
        "quality_issues": [
            {
                "field": q.field_name,
                "rule": q.rule_name,
                "severity": q.severity,
                "description": q.description,
            }
            for q in result.quality_issues
        ],
    }


@app.put("/mapping/session/{session_id}/column", tags=["Mapping"])
def update_column_mapping(
    session_id: str,
    source: str = Query(..., description="Source column name to update"),
    new_target: Optional[str] = Query(None, description="New target column (null to unmap)"),
):
    """
    Manually edit a single column mapping in a pending session.
    Useful for the 'edit' action in the front-end review table.
    """
    result = SESSIONS.get(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    if result.status == "loaded":
        raise HTTPException(status_code=400, detail="Session already loaded, cannot edit")

    # Find and update in auto_matched
    for m in result.mapping.auto_matched:
        if m.source == source:
            m.target = new_target
            m.method = "user"
            m.description = f"Manually set by user to {new_target}"
            return {"updated": True, "source": source, "new_target": new_target}

    # Find in ai_suggestions
    for m in result.mapping.ai_suggestions:
        if m.source == source:
            m.target = new_target
            m.method = "user"
            m.description = f"Manually set by user to {new_target}"
            return {"updated": True, "source": source, "new_target": new_target}

    # Find in unmatched
    for m in result.mapping.unmatched:
        if m.source == source:
            if new_target:
                # Move from unmatched to auto_matched
                m.target = new_target
                m.method = "user"
                m.description = f"Manually mapped by user to {new_target}"
                result.mapping.auto_matched.append(m)
                result.mapping.unmatched.remove(m)
            return {"updated": True, "source": source, "new_target": new_target}

    raise HTTPException(status_code=404, detail=f"Column '{source}' not found in session")


# ---------------------------------------------------------------------------
# Quality & staging endpoints
# ---------------------------------------------------------------------------

@app.get("/mapping/staging", tags=["Staging"])
def get_staging_overview():
    """Return row counts for all staging tables."""
    summary = get_staging_summary()
    return {
        "tables": [
            {"table": table, "rows": count}
            for table, count in summary.items()
        ],
        "total_rows": sum(summary.values()),
    }


@app.get("/mapping/staging/{table_name}", tags=["Staging"])
def get_staging_table_preview(
    table_name: str,
    limit: int = Query(20, le=500),
    offset: int = Query(0, ge=0),
):
    """Get a paginated preview of a staging table's data."""
    df = STAGING_DB.get(table_name)
    if df is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    total = len(df)
    page = df.iloc[offset: offset + limit]

    return {
        "table": table_name,
        "total_rows": total,
        "offset": offset,
        "limit": limit,
        "columns": list(page.columns),
        "rows": page.where(page.notna(), None).to_dict(orient="records"),
    }


@app.get("/mapping/quality/{session_id}", response_model=List[QualityIssueResponse], tags=["Quality"])
def get_quality_issues(session_id: str):
    """Get data quality issues detected after loading a session."""
    result = SESSIONS.get(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return [
        QualityIssueResponse(
            entity_name=q.entity_name,
            field_name=q.field_name,
            record_key=q.record_key,
            rule_name=q.rule_name,
            old_value=q.old_value,
            severity=q.severity,
            description=q.description,
        )
        for q in result.quality_issues
    ]


@app.get("/mapping/available-columns/{table_name}", tags=["Mapping"])
def get_available_columns(table_name: str):
    """Return the list of available target columns for a staging table. Used by front-end dropdowns."""
    from mapping.profiles import STAGING_SCHEMAS
    schema = STAGING_SCHEMAS.get(table_name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return {
        "table": table_name,
        "columns": [c for c in schema["columns"] if c != "coId"],
    }


@app.get("/mapping/tables", tags=["Mapping"])
def list_staging_tables():
    """List all available staging table names."""
    from mapping.profiles import STAGING_SCHEMAS
    return {"tables": list(STAGING_SCHEMAS.keys())}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "online",
        "mode": "offline-capable",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
