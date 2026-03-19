"""
In-memory data store (infrastructure layer).

Holds:
  - CLINICS     : List[Clinic]
  - SESSIONS    : Dict[str, MappingSession]
  - STAGING_DB  : Dict[str, pd.DataFrame]

This module is the single source of truth for runtime state.
Swap this out with a real DB adapter when needed.
"""
import os
import json
import pandas as pd
from typing import Dict, List, Optional

from domain.entities.clinic import Clinic
from domain.entities.mapping_session import MappingSession
from domain.entities.device import Device
from domain.entities.alert import Alert
from infrastructure.mapping_engine.profiles import STAGING_SCHEMAS

# Persistence paths
DEVICES_FILE = "data/devices.json"


# ---------------------------------------------------------------------------
# Runtime stores
# ---------------------------------------------------------------------------

_CLINICS: List[Clinic] = []
_SESSIONS: Dict[str, MappingSession] = {}
_DEVICES: List[Device] = []
_ALERTS: List[Alert] = []

_STAGING_DB: Dict[str, pd.DataFrame] = {
    table: pd.DataFrame(columns=schema["columns"])
    for table, schema in STAGING_SCHEMAS.items()
}


# ---------------------------------------------------------------------------
# Clinic CRUD
# ---------------------------------------------------------------------------

def list_clinics() -> List[Clinic]:
    return list(_CLINICS)


def get_clinic_by_id(clinic_id: int) -> Optional[Clinic]:
    return next((c for c in _CLINICS if c.id == clinic_id), None)


def get_clinic_by_name(name: str) -> Optional[Clinic]:
    return next((c for c in _CLINICS if c.name.lower() == name.lower()), None)


def save_clinic(clinic: Clinic) -> Clinic:
    existing = get_clinic_by_id(clinic.id)
    if existing:
        _CLINICS[_CLINICS.index(existing)] = clinic
    else:
        _CLINICS.append(clinic)
    return clinic


def next_clinic_id() -> int:
    return (max((c.id for c in _CLINICS), default=0)) + 1


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

def get_session(session_id: str) -> Optional[MappingSession]:
    return _SESSIONS.get(session_id)


def save_session(session: MappingSession) -> MappingSession:
    _SESSIONS[session.session_id] = session
    return session


# ---------------------------------------------------------------------------
# Staging DB
# ---------------------------------------------------------------------------

def append_to_staging(table_name: str, df: pd.DataFrame) -> int:
    """Append rows to a staging table. Returns the number of rows appended."""
    if table_name not in _STAGING_DB:
        _STAGING_DB[table_name] = df
    else:
        _STAGING_DB[table_name] = pd.concat(
            [_STAGING_DB[table_name], df], ignore_index=True
        )
    return len(df)


def get_staging_table(table_name: str) -> Optional[pd.DataFrame]:
    return _STAGING_DB.get(table_name)


def get_staging_summary() -> Dict[str, int]:
    return {table: len(df) for table, df in _STAGING_DB.items()}


# ---------------------------------------------------------------------------
# Device & Alert Management [NEW]
# ---------------------------------------------------------------------------

def save_device(device: Device) -> Device:
    existing = next((d for d in _DEVICES if d.device_id == device.device_id), None)
    if existing:
        _DEVICES[_DEVICES.index(existing)] = device
    else:
        _DEVICES.append(device)
    
    # Semi-persistence: save to JSON
    _persist_devices()
    return device


def _persist_devices():
    try:
        os.makedirs(os.path.dirname(DEVICES_FILE), exist_ok=True)
        with open(DEVICES_FILE, 'w', encoding='utf-8') as f:
            json.dump([d.to_dict() for d in _DEVICES], f, indent=2)
    except Exception as e:
        print(f"[!] Error persisting devices: {e}")


def load_devices():
    global _DEVICES
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _DEVICES = [Device(**d) for d in data]
        except Exception as e:
            print(f"[!] Error loading devices: {e}")


def get_device(device_id: str) -> Optional[Device]:
    return next((d for d in _DEVICES if d.device_id == device_id), None)


def list_devices(clinic_id: Optional[int] = None) -> List[Device]:
    if clinic_id:
        return [d for d in _DEVICES if d.clinic_id == clinic_id]
    return list(_DEVICES)


def save_alert(alert: Alert) -> Alert:
    _ALERTS.append(alert)
    return alert


def list_alerts(patient_id: Optional[str] = None, limit: int = 50) -> List[Alert]:
    if patient_id:
        return [a for a in _ALERTS if a.patient_id == patient_id][-limit:]
    return _ALERTS[-limit:]
