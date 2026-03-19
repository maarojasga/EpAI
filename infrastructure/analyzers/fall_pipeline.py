"""
Fall detection and movement analysis pipeline.
Implements the IAnalyzer interface using sensor-based logic.
"""
from typing import List, Dict, Optional
from datetime import datetime
from domain.interfaces.analyzer import IAnalyzer
from domain.entities.observation import Observation
from domain.entities.alert import Alert, AlertType


class FallPipelineAnalyzer(IAnalyzer):
    def __init__(self):
        # State per patient: { patient_id: { ... } }
        self.patient_states: Dict[str, dict] = {}
        
        # Configuration
        self.LOW_ACCEL_THRESHOLD = 0.5  # g
        self.IMPACT_THRESHOLD = 2.0     # g
        self.STABLE_ACCEL_THRESHOLD = 1.1 # g
        self.MOVEMENT_THRESHOLD = 5.0    # movement score
        self.IMMOBILE_ALERT_SECONDS = 30 # seconds

    def _get_or_create_state(self, patient_id: str) -> dict:
        if patient_id not in self.patient_states:
            self.patient_states[patient_id] = {
                "isFalling": False,
                "lowAccelerationStarted": None,
                "impactDetected": False,
                "impactMagnitude": 0.0,
                "immobileSeconds": 0,
                "lastTimestamp": None,
                "hasActiveFall": False
            }
        return self.patient_states[patient_id]

    def analyze(self, observation: Observation) -> List[Alert]:
        state = self._get_or_create_state(observation.patient_id)
        alerts = []
        
        now = observation.timestamp
        accel = observation.accel_magnitude
        movement = observation.movement_score
        
        # 1. Fall Detection Logic
        # Phase A: Free fall (Low acceleration)
        if accel < self.LOW_ACCEL_THRESHOLD:
            if not state["lowAccelerationStarted"]:
                state["lowAccelerationStarted"] = now
        
        # Phase B: Impact Detection
        if accel > self.IMPACT_THRESHOLD:
            state["impactDetected"] = True
            state["impactMagnitude"] = max(state["impactMagnitude"], accel)
            
        # Phase C: Confirm Fall (Low accel followed by impact)
        if state["lowAccelerationStarted"] and state["impactDetected"]:
            if not state["hasActiveFall"]:
                alerts.append(Alert(
                    patient_id=observation.patient_id,
                    device_id=observation.device_id,
                    timestamp=now,
                    type=AlertType.FALL,
                    severity="Critical",
                    message="Fall detected! (Free-fall + Impact)",
                    impact_g=state["impactMagnitude"]
                ))
                state["hasActiveFall"] = True
                state["isFalling"] = False # Reset fall phase
                state["lowAccelerationStarted"] = None
                state["impactDetected"] = False
        
        # 2. Immobility Tracking
        if movement < self.MOVEMENT_THRESHOLD:
            if state["lastTimestamp"]:
                delta = (now - state["lastTimestamp"]).total_seconds()
                state["immobileSeconds"] += delta
            
            if state["immobileSeconds"] >= self.IMMOBILE_ALERT_SECONDS:
                # Only alert once per immobility session
                if state["immobileSeconds"] < self.IMMOBILE_ALERT_SECONDS + 2: 
                    alerts.append(Alert(
                        patient_id=observation.patient_id,
                        device_id=observation.device_id,
                        timestamp=now,
                        type=AlertType.IMMOBILITY,
                        severity="Warning",
                        message=f"No movement detected for {int(state['immobileSeconds'])} seconds."
                    ))
        else:
            # 3. Recovery Detection (Movement after a fall)
            if state["hasActiveFall"]:
                alerts.append(Alert(
                    patient_id=observation.patient_id,
                    device_id=observation.device_id,
                    timestamp=now,
                    type=AlertType.RECOVERY,
                    severity="Info",
                    message="Patient is moving again after fall."
                ))
                state["hasActiveFall"] = False
            
            state["immobileSeconds"] = 0
            
        state["lastTimestamp"] = now
        return alerts

    def get_state(self, patient_id: str) -> dict:
        return self.patient_states.get(patient_id, {})
