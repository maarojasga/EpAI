"""
clinic_use_cases.py - Application-layer use cases for clinic management.
"""
from typing import List, Optional

from domain.entities.clinic import Clinic
from infrastructure.storage import in_memory_store as store


def list_clinics() -> List[Clinic]:
    return store.list_clinics()


def get_clinic(clinic_id: int) -> Optional[Clinic]:
    return store.get_clinic_by_id(clinic_id)


def create_or_get_clinic(
    name: str,
    location: str = "",
    system_type: str = "",
    source_file_pattern: str = "",
    country: str = "",
) -> Clinic:
    """Return existing clinic by name, or create a new one."""
    existing = store.get_clinic_by_name(name)
    if existing:
        return existing

    clinic = Clinic(
        id=store.next_clinic_id(),
        name=name,
        location=location,
        system_type=system_type,
        source_file_pattern=source_file_pattern,
        country=country,
    )
    return store.save_clinic(clinic)
