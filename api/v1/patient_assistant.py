"""
Patient Assistant API - Chat and personalized support for patients.
"""
from fastapi import APIRouter, HTTPException, Body, Response
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from infrastructure.mapping_engine.cleaners import extract_numeric_id


from application.assistant import chat_use_cases as use_cases

router = APIRouter(prefix="/patient-assistant", tags=["Patient Assistant"])

class ChatRequest(BaseModel):
    clinic_id: int
    coPatientId: Optional[str] = None
    query: str
    conversation_id: Optional[str] = None


class ProfileRequest(BaseModel):
    clinic_id: int
    coPatientId: str
    first_name: str
    last_name: str
    gender: str
    dob: str


@router.post("/chat")
async def patient_chat(req: ChatRequest):
    """
    Patient chat endpoint.
    Retrieves history if patient_id is found, otherwise gives general info.
    """
    clean_id = str(extract_numeric_id(req.coPatientId)) if req.coPatientId else None
    result = use_cases.process_patient_query(req.clinic_id, clean_id, req.query, req.conversation_id)
    return result



@router.post("/profile/create")
async def create_profile(req: ProfileRequest):
    """
    Register a new patient profile.
    """
    clean_id = str(extract_numeric_id(req.coPatientId))
    profile = use_cases.create_new_profile(
        req.clinic_id, 
        clean_id, 
        {
            "first_name": req.first_name,
            "last_name": req.last_name,
            "gender": req.gender,
            "dob": req.dob
        }
    )
    return {
        "status": "success",
        "message": "Profile created successfully. I can now provide personalized support.",
        "profile": profile
    }


@router.get("/interpret-labs/{clinic_id}/{coPatientId}")
async def interpret_labs(clinic_id: int, coPatientId: str):
    """
    Analyzes the patient's latest labs and explains them in simple language.
    """
    clean_id = str(extract_numeric_id(coPatientId))

    result = use_cases.interpret_patient_labs(clinic_id, clean_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


class SpeakRequest(BaseModel):
    text: str
    language: Optional[str] = None
    speed: float = 1.0

@router.post("/speak")
async def speak_text(req: SpeakRequest):
    """
    Generates offline TTS audio (WAV) from text for the Patient Assistant 
    using the multilingual Kokoro model.
    """
    from infrastructure.analyzers.tts_service import get_tts_engine
    engine = get_tts_engine()
    
    try:
        audio_bytes = engine.speak_to_bytes(req.text, req.language, req.speed)
        return Response(content=audio_bytes, media_type="audio/wav")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import UploadFile, File, Form

@router.post("/interpret-image")
async def interpret_image(
    file: UploadFile = File(...),
    prompt: Optional[str] = Form(None)
):
    """
    Accepts an image or PDF file (e.g. lab results, prescriptions, nursing reports)
    and explains its contents in simple terms to the patient.
    - PDF: extracts text via PyMuPDF. If scanned, uses LLaVA OCR.
    - Image: uses LLaVA Vision to read the content.
    Then passes the extracted text + user prompt to Phi-3 for interpretation.
    """
    valid_types = ('image/', 'application/pdf')
    is_pdf = file.filename.lower().endswith('.pdf') or (file.content_type and 'pdf' in file.content_type)
    is_image = file.content_type and file.content_type.startswith('image/')
    
    if not is_pdf and not is_image:
        raise HTTPException(status_code=400, detail="Only image or PDF files are supported.")

    try:
        content = await file.read()
        result = use_cases.interpret_patient_document(content, is_pdf=is_pdf, prompt=prompt)
        if result.get("status") == "error":
            raise HTTPException(status_code=503, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
