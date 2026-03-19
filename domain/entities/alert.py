"""
Alert entity - represents a detected clinical event (e.g., Fall).
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AlertType(Enum):
    FALL = "FALL"
    RECOVERY = "RECOVERY"
    IMMOBILITY = "IMMOBILITY"
    BED_EXIT = "BED_EXIT"


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

    def to_dict(self):
        return {
            "patient_id": self.patient_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp.isoformat(),
            "type": self.type.value,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
            "impact_g": self.impact_g
        }
