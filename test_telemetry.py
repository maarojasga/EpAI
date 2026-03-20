import json
from application.telemetry import telemetry_use_cases as use_cases
from infrastructure.analyzers.fall_pipeline import FallPipelineAnalyzer

# Reset global analyzer to simulate fresh server start
use_cases._FALL_ANALYZER = FallPipelineAnalyzer()
use_cases.init_default_devices()

data = {
  "coPatientId": "PAT123",
  "coDevice_id": "MAT-1434",
  "coTimestamp": "2026-03-18 10:00:00",
  "coBed_occupied_0_1": 0,
  "coMovement_score_0_100": 100,
  "coAccel_magnitude_g": 4.5,
  "coPressure_zone1_0_100": 0
}

print("=== FIRST REQUEST ===")
alerts1 = use_cases.ingest_sensor_data(data)
print(f"Alerts generated: {len(alerts1)}")
for a in alerts1:
    print(" -", a.type, a.message)

print("\n=== SECOND REQUEST (Identical) ===")
alerts2 = use_cases.ingest_sensor_data(data)
print(f"Alerts generated: {len(alerts2)}")

print("\n=== CURRENT STATE ===")
print(use_cases._FALL_ANALYZER.get_state("PAT123"))

