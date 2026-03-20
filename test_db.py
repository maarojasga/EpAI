import pandas as pd
from infrastructure.storage.postgres_db import engine
from sqlalchemy import text

try:
    with engine.begin() as c:
        for t in ["tbImportLabsData", "tbImportIcd10Data", "tbImportAcData", "tbImportDeviceMotionData", "tbImportDevice1HzMotionData", "tbImportMedicationInpatientData", "tbImportNursingDailyReportsData"]:
            print(f"Dropping \\\"{t}\\\" if exists...")
            c.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE;'))
    print("Cleaned up quoted tables.")
except Exception as e:
    print(e)
