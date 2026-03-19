"""
Device entity - represents a sensor device and its location.
"""
from dataclasses import dataclass


@dataclass
class Device:
    device_id: str
    clinic_id: int
    location: str
    status: str = "online"  # online, offline, error

    def to_dict(self):
        return {
            "device_id": self.device_id,
            "clinic_id": self.clinic_id,
            "location": self.location,
            "status": self.status
        }
