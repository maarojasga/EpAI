"""
Alert entity - represents a detected clinical event (e.g., Fall).
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional



class AlertType(Enum):
    FALL = "FALL"
    RECOVERY = "RECOVERY"
    IMMOBILITY = "IMMOBILITY"
    BED_EXIT = "BED_EXIT"
    NURSING_NOTE = "NURSING_NOTE"


@dataclass
class Alert:
    patient_id: str
    device_id: str
    timestamp: datetime
    type: AlertType
    severity: str  # Critical, Warning, Info
    message: str
    location: str = ""
    impact_g: float = 0.0
    clinic_id: int = 0
    status: str = "ACTIVE" # ACTIVE | RESOLVED
    case_id: Optional[str] = None
    id: Optional[int] = None


    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, 'isoformat') else str(self.timestamp),
            "type": self.type.value,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
            "impact_g": self.impact_g,
            "clinic_id": self.clinic_id,
            "status": self.status,
            "case_id": self.case_id
        }


