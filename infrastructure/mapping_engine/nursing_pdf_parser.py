"""
nursing_pdf_parser.py - Extracts structured nursing reports from PDFs and images.

Supports:
  - Digital PDFs (text-based): regex extraction per page
  - Scanned PDFs (image-based): OCR via LLaVA then regex
  - Raw images (.jpg/.png): OCR via LLaVA then regex
"""
import re
from typing import List, Dict, Any, Optional


def extract_fields_from_text(text: str) -> Dict[str, Any]:
    """
    Extract structured nursing report fields from a text block using regex.
    Works for both clean PDF text and OCR'd text.
    """
    fields = {
        "PatientID": None,
        "CaseID": None,
        "Ward": None,
        "ReportDate": None,
        "Shift": None,
        "NursingNote": None,
    }

    # Patient ID
    m = re.search(r'Patient\s*ID[:\s]+([A-Za-z0-9\-_]+)', text, re.IGNORECASE)
    if m:
        fields["PatientID"] = m.group(1).strip()

    # Case ID
    m = re.search(r'Case\s*ID[:\s]+([A-Za-z0-9\-_]+)', text, re.IGNORECASE)
    if m:
        fields["CaseID"] = m.group(1).strip()

    # Ward / Station
    m = re.search(r'(?:Ward|Station)[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE)
    if m:
        fields["Ward"] = m.group(1).strip()

    # Date
    m = re.search(r'Date[:\s]+([\d\-\.\/]+)', text, re.IGNORECASE)
    if m:
        fields["ReportDate"] = m.group(1).strip()

    # Shift
    m = re.search(r'Shift[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE)
    if m:
        fields["Shift"] = m.group(1).strip()

    # Nursing Note (everything after "Report" keyword)
    m = re.search(r'Report\s*\n(.+)', text, re.IGNORECASE | re.DOTALL)
    if m:
        fields["NursingNote"] = m.group(1).strip()
    else:
        # Fallback: use everything after the last known field
        lines = text.split('\n')
        note_lines = []
        past_header = False
        for line in lines:
            if past_header:
                note_lines.append(line)
            elif any(kw in line.lower() for kw in ['ward:', 'station:', 'shift:']):
                past_header = True
        if note_lines:
            fields["NursingNote"] = '\n'.join(note_lines).strip()

    return fields


def parse_pdf_pages(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extract one structured nursing report per page from a digital PDF.
    Falls back to LLaVA OCR if a page has no extractable text.
    """
    import fitz

    doc = fitz.open("pdf", pdf_bytes)
    reports = []

    for i, page in enumerate(doc):
        text = page.get_text()

        if len(text.strip()) < 30:
            # Scanned page — use Vision AI
            try:
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                from infrastructure.analyzers.vision_service import get_vlm
                vlm = get_vlm()
                if vlm.available:
                    text = vlm.analyze_image(
                        img_bytes,
                        "Transcribe ALL text from this scanned nursing report. "
                        "Include Patient ID, Case ID, Ward, Date, Shift, and the full nursing note."
                    )
            except Exception as e:
                print(f"[NursingPDF] OCR failed on page {i+1}: {e}")
                continue

        if not text.strip():
            continue

        fields = extract_fields_from_text(text)
        fields["_page"] = i + 1
        fields["_raw_text"] = text.strip()
        reports.append(fields)

    return reports


def parse_image(image_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extract structured nursing report from an image via LLaVA OCR.
    """
    from infrastructure.analyzers.vision_service import get_vlm
    vlm = get_vlm()

    if not vlm.available:
        return []

    text = vlm.analyze_image(
        image_bytes,
        "Transcribe ALL text from this nursing report image. "
        "Include Patient ID, Case ID, Ward, Date, Shift, and the full nursing note."
    )

    if not text.strip():
        return []

    fields = extract_fields_from_text(text)
    fields["_page"] = 1
    fields["_raw_text"] = text.strip()
    return [fields]
