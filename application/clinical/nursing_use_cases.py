"""
nursing_use_cases.py - Use cases for handling nursing reports & clinical NLP
"""
import json
import csv
from typing import List, Dict, Any, Optional
from io import StringIO
from pydantic import BaseModel

from infrastructure.mapping_engine.matcher import get_llm

class NursingAnalysisResult(BaseModel):
    symptoms: List[str]
    interventions: List[str]
    evaluation: str
    location: Optional[str] = None
    is_priority: bool
    priority_level: str = "Medium"
    raw_response: Optional[str] = None

def analyze_nursing_note(note_text: str) -> NursingAnalysisResult:
    """
    Uses local Phi-3 (or Gemini) to extract structured info from free text nursing reports.
    """
    if not note_text or not str(note_text).strip():
        return NursingAnalysisResult(
            symptoms=[], interventions=[], evaluation="Unknown", location=None, is_priority=False, priority_level="Medium"
        )

    # Fast heuristic for priority
    is_priority = "@PRIORITY#" in str(note_text)

    llm = get_llm()
    if not llm.available:
        # Fallback if no LLM
        return NursingAnalysisResult(
            symptoms=[],
            interventions=[],
            evaluation="Unknown (LLM unavailable)",
            location=None,
            is_priority=is_priority,
            priority_level="Medium"
        )

    system_prompt = (
        "You are an expert clinical NLP assistant. Extract structured medical info from "
        "the following nursing shift note. The note might be in German or English.\n"
        "Return ONLY a JSON object with this exact structure:\n"
        "{"
        "  \"symptoms\": [\"list of symptoms or complaints, e.g. dyspnea, pain, Übelkeit\"],"
        "  \"interventions\": [\"list of actions taken, e.g. wound dressing, oxygen therapy\"],"
        "  \"evaluation\": \"short summary of outcome, e.g. stable, worsened, condition improved\","
        "  \"location\": \"specific bed or room mentioned, else null\","
        "  \"priority_level\": \"High, Medium, or Low based on the severity of the symptoms\""
        "}"
    )

    try:
        response_text = llm.generate_text(prompt=f"Note: {note_text}", system_prompt=system_prompt, json_mode=True)
        
        # Clean response to extract json
        # Extract everything between the first { and the first match of } that closes it (or just use regex/simple parsing)
        # LLMs often put markdown around it like ```json ... ```
        cleaned = response_text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            parts = cleaned.split("```")
            if len(parts) >= 3:
                cleaned = parts[1].strip()
                
        # Find first {
        start = cleaned.find("{")
        if start >= 0:
            # We'll try to parse from the first { up to the end. If it fails due to extra data,
            # we can try to find the first } that makes it valid, or just let json.loads tell us where the valid part ended?
            # Actually, if we just find the first matching closing brace:
            brace_count = 0
            end = -1
            for i in range(start, len(cleaned)):
                if cleaned[i] == '{':
                    brace_count += 1
                elif cleaned[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            
            if end > start:
                json_str = cleaned[start:end]
                parsed = json.loads(json_str)
                return NursingAnalysisResult(
                    symptoms=parsed.get("symptoms", []),
                    interventions=parsed.get("interventions", []),
                    evaluation=parsed.get("evaluation", "Unknown"),
                    location=parsed.get("location", None),
                    is_priority=is_priority,
                    priority_level=parsed.get("priority_level", "Medium"),
                    raw_response=response_text
                )
    except Exception as e:
        print(f"[NLP] Error parsing note '{note_text}': {e}")
        
    return NursingAnalysisResult(
        symptoms=[], interventions=[], evaluation="Parsing Error", location=None, is_priority=is_priority, priority_level="Medium", raw_response=response_text if 'response_text' in locals() else None
    )

def process_nursing_csv_batch(csv_content: str, clinic_id: int, max_rows: int = 15) -> List[Dict[str, Any]]:
    """
    Parses a CSV of nursing reports and analyzes the first `max_rows` rows.
    If priority is high, generates an Alert.
    """
    from datetime import datetime
    from domain.entities.alert import Alert, AlertType
    from infrastructure.storage import in_memory_store as store
    from infrastructure.mapping_engine.telemetry_cleaner import TelemetryCleaner
    
    cleaner = TelemetryCleaner()
    reader = csv.DictReader(StringIO(csv_content))
    results = []
    
    count = 0
    for row in reader:
        if count >= max_rows:
            break
            
        # The CSV has columns like CaseID, PatientID, Ward, ReportDate, Shift, NursingNote
        note = row.get("NursingNote") or row.get("nursing_note_free_text") or row.get("nursing_note") or row.get("Pflegebericht") or ""
        if note:
            analysis = analyze_nursing_note(note)
            
            raw_patient = row.get("PatientID") or row.get("patient_id")
            patient = cleaner.clean_id(raw_patient)
            
            raw_case = row.get("CaseID") or row.get("case_id")
            case_id = cleaner.clean_id(raw_case)
            if case_id == "UNKNOWN":
                case_id = "" # Fallback for cases
                
            # Strict row dropping rule
            if patient == "UNKNOWN" or not case_id:
                continue
                
            # Nullification formatting
            ward = row.get("Ward") or row.get("ward") or row.get("Station")
            ward = str(ward).strip() if ward else None
            
            report_date = row.get("ReportDate") or row.get("report_date")
            report_date = str(report_date).strip() if report_date else None
            
            shift = row.get("Shift") or row.get("shift")
            shift = str(shift).strip() if shift else None
            
            final_location = f"{ward} - {analysis.location}" if analysis.location and ward else (analysis.location or ward)
                
            row_data = {
                "CaseID": case_id,
                "PatientID": patient,
                "Ward": ward,
                "ReportDate": report_date,
                "Shift": shift,
                "NursingNote": note,
                "Analysis": analysis.dict(),
            }
            results.append(row_data)
            
            if analysis.is_priority:
                alert = Alert(
                    patient_id=patient,
                    device_id="NURSING-REPORT",
                    timestamp=datetime.now(),
                    type=AlertType.NURSING_NOTE,
                    severity="Warning", # Priorities in notes are typically high warnings
                    message=f"Priority flag in shift report: {analysis.evaluation} (Symptoms: {', '.join(analysis.symptoms)})",
                    location=final_location,
                    clinic_id=clinic_id
                )
                store.save_alert(alert)
                
            count += 1
            
    # Persist in DB
    if results:
        store.save_nursing_notes_batch(clinic_id, results)
            
    return results

def process_single_nursing_text(text: str, clinic_id: int) -> Dict[str, Any]:
    """
    Called when a PDF or Image is OCR'd into text.
    Processes it exactly like a CSV row, assuming generic patient data.
    """
    from datetime import datetime
    from domain.entities.alert import Alert, AlertType
    from infrastructure.storage import in_memory_store as store
    
    analysis = analyze_nursing_note(text)
    final_location = analysis.location or "Unknown location"
    
    row_data = {
        "CaseID": "SINGLE_DOC",
        "PatientID": "UNKNOWN_OCR_PATIENT",
        "Ward": "Unknown",
        "ReportDate": str(datetime.now().date()),
        "Shift": "Manual Upload",
        "NursingNote": text,
        "Analysis": analysis.dict(),
    }
    
    if analysis.is_priority:
        alert = Alert(
            patient_id="UNKNOWN_OCR_PATIENT",
            device_id="NURSING-REPORT-DOC",
            timestamp=datetime.now(),
            type=AlertType.NURSING_NOTE,
            severity="Warning",
            message=f"Priority flag in shift document: {analysis.evaluation} (Symptoms: {', '.join(analysis.symptoms)})",
            location=final_location,
            clinic_id=clinic_id
        )
        store.save_alert(alert)
        
    store.save_nursing_notes_batch(clinic_id, [row_data])
        
    return row_data

def summarize_evolution(patient_id: str, case_id: str, notes: List[Dict[str, str]]) -> str:
    """
    Takes a chronological list of nursing notes and generates a summary of the patient's condition evolution.
    """
    if not notes:
        return "Not enough data to generate an evolution summary."
        
    llm = get_llm()
    if not llm.available:
        return "AI is currently unavailable. Cannot generate evolution summary."
        
    system_prompt = (
        "You are an expert clinical AI assistant. "
        "The user will provide chronological nursing shift notes for a patient. "
        "Write a concise, professional summary describing how the patient's condition has evolved over time. "
        "Highlight improvements, deteriorations, or persistent symptoms."
    )
    
    # Sort notes chronologically from oldest to newest just in case
    try:
        sorted_notes = sorted(notes, key=lambda x: str(x.get("date", "")))
    except:
        sorted_notes = notes
        
    prompt_lines = [f"Patient ID: {patient_id} (Case: {case_id})\nChronological Nursing Notes:"]
    for n in sorted_notes:
        prompt_lines.append(f"- [{n.get('date', 'Unknown Date')}]: {n.get('text', '')}")
        
    prompt = "\n".join(prompt_lines)
    
    try:
        response = llm.generate_text(prompt, system_prompt=system_prompt)
        return response
    except Exception as e:
        print(f"[NLP] Error generating evolution summary: {e}")
        return "An error occurred while generating the evolution summary."

