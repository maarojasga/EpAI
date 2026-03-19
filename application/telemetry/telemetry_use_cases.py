"""
Telemetry use cases - orchestrates sensor data ingestion and analysis.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from domain.entities.observation import Observation
from domain.entities.alert import Alert
from domain.entities.device import Device
from infrastructure.storage import in_memory_store as store
from infrastructure.mapping_engine.telemetry_cleaner import TelemetryCleaner
from infrastructure.analyzers.fall_pipeline import FallPipelineAnalyzer


# Global analyzer instance (stateful)
_FALL_ANALYZER = FallPipelineAnalyzer()
_CLEANER = TelemetryCleaner()


def ingest_sensor_data(raw_data: Dict[str, Any]) -> List[Alert]:
    """
    Cleans raw sensor data, performs analysis, and persists any detected alerts.
    """
    # 1. Clean
    cleaned_dict = _CLEANER.process_row(raw_data)
    
    # 2. Map to Entity
    observation = Observation(
        patient_id=cleaned_dict["patient_id"],
        device_id=cleaned_dict["device_id"],
        timestamp=cleaned_dict["timestamp"],
        bed_occupied=cleaned_dict["bed_occupied"],
        movement_score=cleaned_dict["movement_score"],
        accel_magnitude=cleaned_dict["accel_magnitude"],
        pressure_zones=cleaned_dict["pressure_zones"]
    )
    
    # 3. Analyze
    new_alerts = _FALL_ANALYZER.analyze(observation)
    
    # 4. Enrich & Persist
    for alert in new_alerts:
        device = store.get_device(alert.device_id)
        if device:
            alert.location = device.location
        store.save_alert(alert)
        
    return new_alerts


def get_latest_alerts(patient_id: Optional[str] = None, limit: int = 20) -> List[Alert]:
    return store.list_alerts(patient_id, limit)


def register_device(device_id: str, clinic_id: int, location: str) -> Device:
    device = Device(device_id=device_id, clinic_id=clinic_id, location=location)
    return store.save_device(device)


def get_all_devices(clinic_id: Optional[int] = None) -> List[Device]:
    return store.list_devices(clinic_id)


def init_default_devices():
    """Seed some devices for demonstration if none exist."""
    # 1. Try to load from persistent store
    store.load_devices()
    
    # 2. If still empty, register defaults
    if not store.list_devices():
        register_device("MAT-1434", 1, "Room 101, Bed A")
        register_device("MAT-7873", 1, "Room 101, Bed B")
        register_device("MAT-5012", 2, "Emergency Ward, Bay 1")
        register_device("MAT-9279", 2, "Emergency Ward, Bay 2")
        register_device("MAT-4527", 3, "Intensive Care, Unit 4")
        register_device("MAT-6574", 4, "Nursing Home, Wing C")
