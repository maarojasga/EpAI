"""
Clinic entity - pure domain model, no framework dependencies.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Clinic:
    id: int
    name: str
    location: str = ""
    system_type: str = ""          # SAP | IID | CSV_SIMPLE | etc.
    source_file_pattern: str = ""  # e.g. 'clinic_1_*', 'epaAC-Data-2*'
    country: str = ""              # DE | CH | AT | etc.

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "system_type": self.system_type,
            "source_file_pattern": self.source_file_pattern,
            "country": self.country,
        }
