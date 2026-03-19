"""
Telemetry API - real-time sensor data ingestion and alerting.
"""
from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from application.telemetry import telemetry_use_cases as use_cases


router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


class DeviceMapRequest(BaseModel):
    device_id: str
    clinic_id: int
    location: str


@router.post("/ingest")
async def ingest_telemetry(data: Dict[str, Any] = Body(...)):
    """
    Receive sensor data packet (1Hz).
    Processes it through the FallDetection pipeline.
    """
    alerts = use_cases.ingest_sensor_data(data)
    return {
        "status": "success",
        "alerts_detected": len(alerts),
        "alerts": [a.to_dict() for a in alerts]
    }


@router.get("/alerts")
async def get_alerts(patient_id: Optional[str] = None, limit: int = 20):
    """
    Retrieve clinical alerts (Falls, Immobility).
    """
    alerts = use_cases.get_latest_alerts(patient_id, limit)
    return [a.to_dict() for a in alerts]


@router.get("/devices")
async def get_devices(clinic_id: Optional[int] = None):
    """
    Get all registered devices and their locations.
    """
    devices = use_cases.get_all_devices(clinic_id)
    return [d.to_dict() for d in devices]


@router.post("/devices/map")
async def map_device(req: DeviceMapRequest):
    """
    Associate a Device ID with a Clinic and Location.
    """
    device = use_cases.register_device(req.device_id, req.clinic_id, req.location)
    return device.to_dict()


# Initialize some dummy data for the demo
use_cases.init_default_devices()
