"""
TelemetryCleaner - sanitizes noisy sensor data (telemetry) from CSV/API.
Handles artifacts like #, @, ä, and standardizes missing values.
"""
import re
import pandas as pd
from datetime import datetime
from typing import Any, Dict, Optional


class TelemetryCleaner:
    def __init__(self):
        self.char_blacklist = re.compile(r'[#@ß^%öäü$]')

    def clean_id(self, val: Any) -> str:
        if pd.isna(val) or str(val).lower() in ['nan', 'null', 'n/a', 'unknown', 'missing', '']:
            return "UNKNOWN"
        # Remove special characters
        clean_val = self.char_blacklist.sub('', str(val)).strip()
        return clean_val

    def clean_float(self, val: Any, default: float = 0.0) -> float:
        if pd.isna(val):
            return default
        s_val = str(val).lower().strip()
        if s_val in ['nan', 'null', 'n/a', 'unknown', 'missing', '', ' ']:
            return default
        
        # Remove any non-numeric chars (except decimal point and minus)
        clean_s = re.sub(r'[^-0-9.]', '', s_val)
        try:
            return float(clean_s)
        except ValueError:
            return default

    def clean_bool(self, val: Any) -> bool:
        if pd.isna(val):
            return False
        s_val = str(val).lower().strip()
        if s_val in ['1', 'true', 'yes', 'y']:
            return True
        return False

    def clean_timestamp(self, val: Any) -> datetime:
        if pd.isna(val):
            return datetime.now()
        s_val = str(val).lower().strip()
        if s_val in ['nan', 'null', 'n/a', 'unknown', 'missing', '', ' ']:
            return datetime.now()
        
        # Remove artifacts
        clean_s = self.char_blacklist.sub('', s_val).strip()
        try:
            # Try common formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    return datetime.strptime(clean_s, fmt)
                except:
                    continue
            return datetime.now()
        except:
            return datetime.now()

    def process_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a raw dictionary from CSV and returns a cleaned version
        compatible with the Observation entity.
        Supports both "good" and "bad" header styles.
        """
        # Mapping bad headers to good internal names
        # Bad: PatientID, DeviceID, Timestamp, BedOccupied, MovementScore, AccelMag
        # Good: patient_id, device_id, timestamp, bed_occupied, movement_score, accel_magnitude
        
        get = lambda *keys: next((row[k] for k in keys if k in row), None)

        return {
            "patient_id": self.clean_id(get("coPatientId", "coPatient_id", "patient_id", "PatientID", "patientID")),
            "device_id": self.clean_id(get("coDeviceId", "coDevice_id", "device_id", "DeviceID", "deviceID")),
            "timestamp": self.clean_timestamp(get("coTimestamp", "timestamp", "Timestamp")),
            "bed_occupied": self.clean_bool(get("coBed_occupied_0_1", "bed_occupied", "BedOccupied")),
            "movement_score": self.clean_float(get("coMovement_score_0_100", "movement_score", "MovementScore")),
            "accel_magnitude": self.clean_float(get("coAccel_magnitude_g", "accel_magnitude", "AccelMag")),
            "pressure_zones": {
                "zone1": self.clean_float(get("coPressure_zone1_0_100", "pressure_zone1_0_100", "PressZ1", "pressZ1")),
                "zone2": self.clean_float(get("coPressure_zone2_0_100", "pressure_zone2_0_100", "PressZ2", "pressZ2")),
                "zone3": self.clean_float(get("coPressure_zone3_0_100", "pressure_zone3_0_100", "PressZ3", "pressZ3")),
                "zone4": self.clean_float(get("coPressure_zone4_0_100", "pressure_zone4_0_100", "PressZ4", "pressZ4"))
            }
        }
