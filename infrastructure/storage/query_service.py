"""
query_service.py - Retrieval of harmonized clinical data for LLM context.
"""
from typing import List, Dict, Any, Optional
import pandas as pd
from infrastructure.storage import in_memory_store as store # Using store as proxy for demo

def get_patient_summary(clinic_id: int, local_patient_id: str) -> Optional[str]:
    """
    Fetches all clinical history for a patient across all harmonized tables.
    Returns a string representation ready for LLM context.
    """
    # 1. Resolve Person ID from Patient Mapping
    # (In a real DB, this would be a JOIN across tbPatientMapping and clinical tables)
    # For the hackathon demo, we check if the patient exists in our registered mappings.
    
    mapping = store.get_patient_mapping(clinic_id, local_patient_id)
    if not mapping:
        return None
        
    person_id = mapping["person_id"]
    
    # 2. Fetch history (Mocking retrieval from harmonized tables)
    # In production: SELECT * FROM tbObservation/tbCondition/tbMedicationPlan WHERE coPersonId = person_id
    
    history_blocks = []
    history_blocks.append(f"### Historical Data for Patient {local_patient_id} (Internal ID: {person_id})")
    
    # Simulating some retrieved data for the demo
    # In a real scenario, this comes from the SQL DB via SQLAlchemy or similar
    observations = [
        {"timestamp": "18.03.2026 10:00", "concept": "HbA1c", "value": "6.5", "unit": "%"},
        {"timestamp": "15.03.2026 09:30", "concept": "Blood Pressure", "value": "130/85", "unit": "mmHg"},
    ]
    
    history_blocks.append("\n#### Observations:")
    for obs in observations:
        history_blocks.append(f"- {obs['timestamp']}: {obs['concept']} = {obs['value']} {obs['unit']}")
        
    conditions = ["Type 2 Diabetes Mellitus", "Essential Hypertension"]
    history_blocks.append("\n#### Conditions:")
    for cond in conditions:
        history_blocks.append(f"- {cond}")
        
    medications = ["Metformin 500mg BID", "Lisinopril 10mg QD"]
    history_blocks.append("\n#### Medications:")
    for med in medications:
        history_blocks.append(f"- {med}")
        
    return "\n".join(history_blocks)

def create_patient_profile(clinic_id: int, local_patient_id: str, details: Dict[str, Any]):
    """
    Creates a new entry in tbPerson and tbPatientMapping.
    """
    # Logic to insert into DB
    return store.register_patient(clinic_id, local_patient_id, details)
