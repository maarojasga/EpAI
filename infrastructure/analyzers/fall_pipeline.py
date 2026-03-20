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

    def _get_or_create_state(self, patient_id: str) -> dict:
        if patient_id not in self.patient_states:
            self.patient_states[patient_id] = {
                "activeFall": False,
                "fallCount": 0,
                "impactG": 0.0,
                "immobileSeconds": 0,
                "recoveryCounter": 0,
                "lastTimestamp": None,
                "lastImmobilityMin": None
            }
        return self.patient_states[patient_id]

    def analyze(self, observation: Observation) -> List[Alert]:
        state = self._get_or_create_state(observation.patient_id)
        alerts = []
        
        now = observation.timestamp
        accel = observation.accel_magnitude
        mv = observation.movement_score
        
        # Calculate pressure average if available
        press_dict = observation.pressure_zones or {}
        press_vals = list(press_dict.values())
        press_avg = sum(press_vals) / max(1, len(press_vals)) if press_vals else 50.0  # safe default
        
        bed_occupied = observation.bed_occupied
        if bed_occupied is None:
            bed_occupied = 1 # assume occupied

        # ── STAGE 1: Fall Detection ──
        fall_score = 0
        if accel > 2.0: fall_score += 40
        if mv > 80: fall_score += 30
        if press_avg < 10: fall_score += 20
        if bed_occupied == 0: fall_score += 10
        
        fall_detected = fall_score >= 70

        if fall_detected and not state["activeFall"]:
            state["activeFall"] = True
            state["impactG"] = accel
            state["immobileSeconds"] = 0
            state["recoveryCounter"] = 0
            state["fallCount"] += 1
            
            severity = "Critical" if accel > 4 else "Warning"
            
            alerts.append(Alert(
                patient_id=observation.patient_id,
                device_id=observation.device_id,
                timestamp=now,
                type=AlertType.FALL,
                severity=severity,
                message=f"Fall detected! (Score {fall_score}/100, Impact {accel:.2f}g)",
                impact_g=accel
            ))

        # ── STAGE 2: Impact Magnitude ──
        if fall_detected:
            state["impactG"] = accel

        # ── STAGE 3: Immobility Tracking ──
        if state["activeFall"] and not fall_detected:
            # We assume tick duration is roughly difference in timestamps or 1 second
            delta_sec = 1
            if state["lastTimestamp"]:
                delta_sec = max(1, (now - state["lastTimestamp"]).total_seconds())
                
            if mv <= 10:
                state["immobileSeconds"] += delta_sec
                
                # We can fire an immobility alert every 30 seconds of immobility for example
                modulo_threshold = 30
                if state["immobileSeconds"] > 0 and int(state["immobileSeconds"]) % modulo_threshold == 0:
                    alerts.append(Alert(
                        patient_id=observation.patient_id,
                        device_id=observation.device_id,
                        timestamp=now,
                        type=AlertType.IMMOBILITY,
                        severity="Warning",
                        message=f"Post-fall immobility alert: patient unmoving for {int(state['immobileSeconds'])} seconds."
                    ))

            # Recovery: sustained movement > 15 for 5+ seconds
            if mv > 15:
                state["recoveryCounter"] += 1
                if state["recoveryCounter"] > 5:
                    state["activeFall"] = False
                    state["lastImmobilityMin"] = state["immobileSeconds"] / 60.0
                    state["recoveryCounter"] = 0
                    
                    alerts.append(Alert(
                        patient_id=observation.patient_id,
                        device_id=observation.device_id,
                        timestamp=now,
                        type=AlertType.RECOVERY,
                        severity="Info",
                        message=f"Patient recovered from fall. Total immobility time: {state['lastImmobilityMin']:.1f} minutes."
                    ))
            else:
                state["recoveryCounter"] = 0

        state["lastTimestamp"] = now
        return alerts

    def get_state(self, patient_id: str) -> dict:
        return self.patient_states.get(patient_id, {})
