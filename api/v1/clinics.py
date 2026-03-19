"""
api/v1/clinics.py - Clinic management endpoints.
"""
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from application.clinics.clinic_use_cases import (
    list_clinics,
    get_clinic,
    create_or_get_clinic,
)

router = APIRouter(prefix="/clinics", tags=["Clinics"])


class ClinicCreate(BaseModel):
    name: str
    location: str = ""
    system_type: str = ""
    source_file_pattern: str = ""
    country: str = ""


class ClinicResponse(BaseModel):
    id: int
    name: str
    location: str
    system_type: str
    source_file_pattern: str
    country: str


@router.get("", response_model=List[ClinicResponse])
def get_clinics():
    """List all registered clinics."""
    return [ClinicResponse(**c.to_dict()) for c in list_clinics()]


@router.get("/{clinic_id}", response_model=ClinicResponse)
def get_clinic_by_id(clinic_id: int):
    """Get a single clinic by ID."""
    clinic = get_clinic(clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail=f"Clinic {clinic_id} not found")
    return ClinicResponse(**clinic.to_dict())


@router.post("", response_model=ClinicResponse, status_code=201)
def create_clinic(body: ClinicCreate):
    """
    Register a new clinic. If a clinic with the same name already exists,
    it is returned instead (idempotent).
    """
    clinic = create_or_get_clinic(
        name=body.name,
        location=body.location,
        system_type=body.system_type,
        source_file_pattern=body.source_file_pattern,
        country=body.country,
    )
    return ClinicResponse(**clinic.to_dict())
