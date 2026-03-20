"""
api/v1/clinical.py - Endpoints for clinical staff applications
"""
from fastapi import APIRouter, File, UploadFile, HTTPException
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from application.clinical import nursing_use_cases

router = APIRouter(prefix="/clinical", tags=["Clinical"])

def _sort_nursing_results(results: List[Dict[str, Any]]) -> None:
    """
    Sorts nursing reports keeping same PatientID and CaseID together, 
    but ordered from newest to oldest.
    """
    # 1. Sort by Date DESC
    results.sort(key=lambda x: str(x.get("ReportDate") or ""), reverse=True)
    # 2. Stable sort by CaseID ASC
    results.sort(key=lambda x: str(x.get("CaseID") or ""))
    # 3. Stable sort by PatientID ASC
    results.sort(key=lambda x: str(x.get("PatientID") or ""))



@router.post("/nursing/upload/{clinic_id}")
async def upload_nursing_reports(
    clinic_id: int,
    file: UploadFile = File(...)
):
    """
    Upload a CSV, PDF, or Image of nursing daily reports.
    - CSV: processes rows directly with NLP.
    - PDF: extracts structured data PER PAGE using regex + OCR fallback, then runs NLP.
    - Image: OCRs the image via LLaVA, extracts fields, then runs NLP.

    Returns editable structured data. Rows missing PatientID or CaseID are flagged.
    """
    valid_exts = ('.csv', '.pdf', '.jpg', '.jpeg', '.png')
    if not any(file.filename.lower().endswith(ext) for ext in valid_exts):
        raise HTTPException(
            status_code=400,
            detail="Only CSV, PDF, or Image files are supported."
        )

    try:
        content = await file.read()

        if file.filename.lower().endswith('.csv'):
            text_content = content.decode("utf-8", errors="replace")
            # Increased max_rows to handle reasonable daily logs
            results = nursing_use_cases.process_nursing_csv_batch(text_content, clinic_id, max_rows=100)
            
            _sort_nursing_results(results)
            
            return {
                "status": "success",
                "source": "csv",
                "message": f"Processed {len(results)} nursing reports with NLP analysis.",
                "editable": True,
                "data": results
            }

        # ── PDF or Image ──
        from infrastructure.mapping_engine.nursing_pdf_parser import (
            parse_pdf_pages, parse_image
        )

        if file.filename.lower().endswith('.pdf'):
            raw_reports = parse_pdf_pages(content)
            source = "pdf"
        else:
            raw_reports = parse_image(content)
            source = "image"

        if not raw_reports:
            raise HTTPException(
                status_code=422,
                detail="Could not extract any nursing reports. Ensure the file is readable or the Vision model is loaded."
            )

        # Run NLP analysis on extracted nursing notes and build results
        from infrastructure.mapping_engine.telemetry_cleaner import TelemetryCleaner
        cleaner = TelemetryCleaner()
        
        results = []
        skipped = 0
        for report in raw_reports:
            patient_id = cleaner.clean_id(report.get("PatientID"))
            if patient_id == "UNKNOWN": patient_id = ""
            
            case_id = cleaner.clean_id(report.get("CaseID"))
            if case_id == "UNKNOWN": case_id = ""
            
            note = report.get("NursingNote") or ""

            # Flag missing mandatory fields but still include for editing
            is_valid = bool(patient_id and case_id)

            analysis_data = {}
            if note:
                analysis = nursing_use_cases.analyze_nursing_note(note)
                analysis_data = analysis.dict()

            row = {
                "PatientID": patient_id,
                "CaseID": case_id,
                "Ward": report.get("Ward"),
                "ReportDate": report.get("ReportDate"),
                "Shift": report.get("Shift"),
                "NursingNote": note,
                "Analysis": analysis_data,
                "_page": report.get("_page"),
                "_valid": is_valid,
                "_validation_errors": []
            }

            if not patient_id:
                row["_validation_errors"].append("Missing PatientID (required)")
            if not case_id:
                row["_validation_errors"].append("Missing CaseID (required)")
            if not is_valid:
                skipped += 1

            results.append(row)

        _sort_nursing_results(results)

        valid_count = len(results) - skipped
        return {
            "status": "success",
            "source": source,
            "message": f"Extracted {len(results)} reports ({valid_count} valid, {skipped} need review).",
            "editable": True,
            "total_pages": len(results),
            "valid_reports": valid_count,
            "needs_review": skipped,
            "data": results
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class EvolutionNote(BaseModel):
    date: str
    text: str

class EvolutionRequest(BaseModel):
    coPatientId: str
    coCaseId: str
    notes: List[EvolutionNote]

@router.post("/nursing/evolution")
def generate_evolution_summary(req: EvolutionRequest):
    """
    Generates an AI summary of how the patient's condition evolved over the provided chronological notes.
    """
    try:
        notes_dict = [{"date": n.date, "text": n.text} for n in req.notes]
        summary = nursing_use_cases.summarize_evolution(req.coPatientId, req.coCaseId, notes_dict)
        return {
            "status": "success",
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nursing/history/{clinic_id}/{coPatientId}")
def get_nursing_history(clinic_id: int, coPatientId: str):
    """
    Retrieves the chronological history of nursing reports for a patient.
    """
    try:
        from infrastructure.storage import in_memory_store as store
        history = store.list_nursing_history(clinic_id, coPatientId)
        return {
            "status": "success",
            "patient_id": coPatientId,
            "clinic_id": clinic_id,
            "data": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
