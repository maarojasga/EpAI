"""
Observation entity - represents a single telemetry packet from a sensor device.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class Observation:
    patient_id: str
    device_id: str
    timestamp: datetime
    
    # Motion Data
    bed_occupied: bool = False
    movement_score: float = 0.0
    accel_magnitude: float = 0.0
    
    # Pressure Data (0-100)
    pressure_zones: Dict[str, float] = field(default_factory=lambda: {
        "zone1": 0.0,
        "zone2": 0.0,
        "zone3": 0.0,
        "zone4": 0.0
    })
    
    # Metadata / Raw Data
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "patient_id": self.patient_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp.isoformat(),
            "bed_occupied": self.bed_occupied,
            "movement_score": self.movement_score,
            "accel_magnitude": self.accel_magnitude,
            "pressure_zones": self.pressure_zones,
        }
