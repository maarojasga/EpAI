"""
chat_use_cases.py - Logic for the Patient Assistant Chat.
"""
from typing import Dict, Any, List, Optional
from infrastructure.storage import query_service
from domain.entities.alert import Alert # Reusing Alert for simple messaging

def process_patient_query(clinic_id: int, patient_id: Optional[str], query: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Main logic for the patient assistant.
    1. Always answer the patient's question using the LLM.
    2. If patient_id is provided AND found, enrich with medical history.
    3. Maintain conversation history via conversation_id.
    """
    import uuid
    from infrastructure.mapping_engine.matcher import get_llm
    from infrastructure.storage import in_memory_store as store

    # Generate or reuse conversation_id
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    context = None
    if patient_id:
        context = query_service.get_patient_summary(clinic_id, patient_id)

    # System prompt
    system_prompt = (
        "You are a kind, empathetic, and knowledgeable medical assistant talking directly to a patient. "
        "Answer their health question in simple, jargon-free language. "
        "Always remind them to consult their physician for clinical decisions. "
        "Do NOT diagnose. Be warm and supportive. "
        "CRITICAL: You MUST reply in the SAME language the patient uses. "
        "If they write in Spanish, reply in Spanish. If German, reply in German. If English, reply in English. "
        "Always match their language exactly."
    )

    if context:
        system_prompt += f"\n\nThis patient's medical history:\n{context}"
        status = "personalized"
    else:
        status = "generic"

    # Save the user message to conversation history
    store.append_to_conversation(conversation_id, "user", query)

    # Build messages array for LLM (last 10 exchanges max for speed)
    history = store.get_conversation(conversation_id)
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-20:]:  # last 10 pairs (user+assistant)
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Generate response via LLM
    llm = get_llm()
    if llm._mode == "online":
        # Online mode: use Claude multi-turn chat
        try:
            response = llm.claude_chat_completion(
                messages=messages[1:],  # exclude system msg (Claude handles it separately)
                system_prompt=system_prompt,
                max_tokens=1024
            )
            if not response:
                raise RuntimeError("Empty Claude response")
        except Exception as e:
            print(f"[Chat] Claude error: {e}")
            response = (
                f"Thank you for your question: '{query}'. "
                "Our AI assistant encountered an error. "
                "Please try again or consult your healthcare provider."
            )
    elif llm.available:
        try:
            out = llm.local_llm.create_chat_completion(
                messages=messages,
                max_tokens=512,
                temperature=0.3
            )
            response = out["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[Chat] LLM error: {e}")
            response = llm.generate_text(
                f"A patient asks: {query}\n\nPlease answer their question helpfully.",
                system_prompt=system_prompt
            )
    else:
        response = (
            f"Thank you for your question: '{query}'. "
            "Unfortunately, our AI assistant is temporarily unavailable. "
            "Please consult your healthcare provider for medical advice."
        )

    # Save assistant response to history
    store.append_to_conversation(conversation_id, "assistant", response)

    # Build result
    result = {
        "conversation_id": conversation_id,
        "response": response,
        "status": status,
        "context_found": context is not None,
        "messages_in_history": len(store.get_conversation(conversation_id)),
    }

    # Suggest providing patient_id only if not provided or not found
    if not context:
        result["suggest_profile"] = True
        # Detect language from query for the hint
        _q = query.lower()
        if any(w in _q for w in ['qué', 'cómo', 'por', 'tengo', 'puedo', 'hola', 'dolor', 'tomo']):
            result["profile_hint"] = (
                "Si deseas que lleve un seguimiento de tu progreso y te dé apoyo personalizado, "
                "puedes proporcionarme tu ID de Paciente. Si no, ¡sigue preguntando con confianza!"
            )
        elif any(w in _q for w in ['was', 'wie', 'ich', 'mein', 'kann', 'habe', 'arzt']):
            result["profile_hint"] = (
                "Wenn Sie möchten, dass ich Ihren Fortschritt verfolge, können Sie Ihre Patienten-ID angeben. "
                "Ansonsten können Sie gerne weiter Fragen stellen!"
            )
        else:
            result["profile_hint"] = (
                "If you'd like me to track your progress and give you personalized support, "
                "you can provide your Patient ID. Otherwise, feel free to keep asking questions!"
            )

    return result

def create_new_profile(clinic_id: int, patient_id: str, details: Dict[str, Any]):
    return query_service.create_patient_profile(clinic_id, patient_id, details)

def interpret_patient_labs(clinic_id: int, patient_id: str) -> Dict[str, Any]:
    """
    Fetches the patient summary (which includes labs) and uses Phi-3 to explain them
    in simple, patient-friendly terms.
    """
    context = query_service.get_patient_summary(clinic_id, patient_id)
    if not context:
        return {
            "status": "error",
            "message": f"Couldn't find any lab records for patient {patient_id} in clinic {clinic_id}."
        }
        
    from infrastructure.mapping_engine.matcher import get_llm
    llm = get_llm()
    if not llm.available:
        return {
            "status": "error",
            "message": "AI interpretation is currently unavailable. Please consult your physician.",
            "raw_context": context
        }
        
    system_prompt = (
        "You are a helpful and empathetic medical assistant talking directly to a patient. "
        "Your task is to explain their recent lab results or health data in simple, jargon-free language. "
        "Highlight any values that are out of normal range, but always reassure them and tell them "
        "to consult their doctor for clinical advice. Do NOT give medical diagnoses."
    )
    
    prompt = f"Here is the patient's data:\n\n{context}\n\nPlease explain these results to me simply."
    
    explanation = llm.generate_text(prompt, system_prompt=system_prompt)
    
    return {
        "status": "success",
        "explanation": explanation,
        "raw_context": context
    }

def interpret_patient_image(image_bytes: bytes, prompt: Optional[str] = None) -> Dict[str, Any]:
    """Legacy wrapper — delegates to interpret_patient_document."""
    return interpret_patient_document(image_bytes, is_pdf=False, prompt=prompt)


def interpret_patient_document(file_bytes: bytes, is_pdf: bool = False, prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Interprets a patient-uploaded document (image or PDF).
    1. Extracts text from the document (PyMuPDF for PDFs, LLaVA for images/scanned).
    2. Passes extracted text + user prompt to Phi-3 for patient-friendly explanation.
    """
    from infrastructure.mapping_engine.matcher import get_llm
    from infrastructure.analyzers.vision_service import get_vlm

    extracted_text = ""

    if is_pdf:
        # Try digital text extraction first
        try:
            import fitz
            doc = fitz.open("pdf", file_bytes)
            for page in doc:
                extracted_text += page.get_text() + "\n"

            # If scanned (very little text), use LLaVA on first pages
            if len(extracted_text.strip()) < 50 and len(doc) > 0:
                vlm = get_vlm()
                if vlm.available:
                    for i, page in enumerate(doc[:3]):  # OCR first 3 pages max
                        pix = page.get_pixmap(dpi=150)
                        img_bytes = pix.tobytes("png")
                        page_text = vlm.analyze_image(img_bytes, "Transcribe ALL text from this medical document page.")
                        extracted_text += page_text + "\n"
        except Exception as e:
            print(f"[PatientDoc] PDF extraction error: {e}")
    else:
        # Image — use LLaVA to read content
        vlm = get_vlm()
        if vlm.available:
            extracted_text = vlm.analyze_image(file_bytes, "Transcribe ALL text visible in this medical document or lab result image.")
        else:
            return {
                "status": "error",
                "message": "Vision AI is currently unavailable. Please consult your physician."
            }

    if not extracted_text.strip():
        return {
            "status": "error",
            "message": "Could not extract any readable text from the uploaded file."
        }

    # Now use Phi-3 to interpret the extracted text based on the user's prompt
    default_prompt = "¿Qué indican estos resultados?"
    user_prompt = prompt if prompt else default_prompt

    system_prompt = (
        "You are a kind, empathetic medical assistant explaining medical documents to a patient. "
        "Use simple, jargon-free language. Highlight important findings. "
        "Always remind them to consult their physician. Do NOT diagnose."
    )

    full_prompt = (
        f"The patient uploaded a medical document. Here is the extracted text:\n\n"
        f"---\n{extracted_text[:3000]}\n---\n\n"
        f"The patient asks: {user_prompt}\n\n"
        "Please answer their question based on the document content."
    )

    llm = get_llm()
    if llm.available:
        explanation = llm.generate_text(full_prompt, system_prompt=system_prompt)
    else:
        explanation = f"Here is the text extracted from your document:\n\n{extracted_text[:2000]}\n\nPlease consult your physician for interpretation."

    return {
        "status": "success",
        "explanation": explanation,
        "extracted_text": extracted_text[:2000],
        "source": "pdf" if is_pdf else "image"
    }

