"""
pdf_extract.py - Extract structured clinical data from PDFs or free-text reports using LLM.
"""

import os
import fitz  # PyMuPDF
from typing import Dict, Any, Optional
from infrastructure.mapping_engine.matcher import LLMManager

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract raw text from a PDF file. If it's a scanned PDF (no text),
    use VisionManager (LLaVA) to extract text from the first page image.
    """
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
                
            # If less than 50 chars, it's likely a scanned image PDF
            if len(text.strip()) < 50 and len(doc) > 0:
                print(f"[PDF Extract] PDF appears scanned. Using Vision AI...")
                first_page = doc[0]
                pix = first_page.get_pixmap(dpi=150)
                image_bytes = pix.tobytes("jpeg")
                
                from infrastructure.analyzers.vision_service import get_vlm
                vlm = get_vlm()
                prompt = "Extract all readable text from this scanned medical document."
                extracted = vlm.analyze_image(image_bytes, prompt)
                return extracted
                
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
    return text

def extract_structured_data(text: str, models_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Use LLM to extract structured entities from clinical free-text.
    Targeting: Patient Info, Diagnoses, Medications, and Vitals.
    """
    llm = LLMManager(models_dir=models_dir)
    
    system_prompt = "You are a clinical data extraction expert. Return ONLY JSON."
    prompt = f"""
    Extract structured data from the following medical report text.
    Return ONLY a JSON object with these keys:
    - patient_name: string
    - case_id: string
    - admission_date: string (DD.MM.YYYY)
    - diagnoses: list of strings (ICD-10 if possible)
    - procedures: list of strings (OPS if possible)
    - medications: list of strings
    - vitals: {{ "blood_pressure": string, "heart_rate": string, "temp": string }}
    
    If information is missing, use null.
    
    Report Text:
    \"\"\"
    {text[:2000]} 
    \"\"\"
    """
    
    try:
        raw_response = llm.generate_text(prompt, system_prompt=system_prompt, json_mode=True)
        
        # Simple JSON extraction from the string
        import json
        start = raw_response.find("{")
        end = raw_response.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw_response[start:end])
        return {}
    except Exception as e:
        print(f"LLM Extraction failed: {e}")
        return {}

def process_unstructured_file(filepath: str, models_dir: Optional[str] = None) -> Dict[str, Any]:
    """Process a PDF or TXT file and return structured clinical data."""
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == ".pdf":
        text = extract_text_from_pdf(filepath)
    else:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
            
    if not text.strip():
        return {}
        
    return extract_structured_data(text, models_dir=models_dir)
