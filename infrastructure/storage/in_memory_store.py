"""
In-memory data store (infrastructure layer).

Holds:
  - CLINICS     : List[Clinic]
  - INGESTION_JOBS: Dict[str, IngestionJob]
  - STAGING_DB  : Dict[str, pd.DataFrame]


This module is the single source of truth for runtime state.
Swap this out with a real DB adapter when needed.
"""
import os
import json
import logging
import pandas as pd
from typing import Dict, List, Optional, Any

from sqlalchemy import text
from infrastructure.storage.postgres_db import SessionLocal

from domain.entities.clinic import Clinic
from domain.entities.mapping_session import IngestionJob

from domain.entities.device import Device
from domain.entities.alert import Alert
from infrastructure.mapping_engine.profiles import STAGING_SCHEMAS

# --- Configure Logger ---
logger = logging.getLogger(__name__)


# Persistence paths
DEVICES_FILE = "data/devices.json"


# ---------------------------------------------------------------------------
# Runtime stores
# ---------------------------------------------------------------------------

_CLINICS: List[Clinic] = []
# _INGESTION_JOBS y _STAGING_DB se mantienen en memoria para el flujo de trabajo actual,
# pero los datos finales se persisten en Postgres.
_INGESTION_JOBS: Dict[str, IngestionJob] = {}

_DEVICES: List[Device] = []
_ALERTS: List[Alert] = []


# ---------------------------------------------------------------------------
# Clinic CRUD [PostgreSQL]
# ---------------------------------------------------------------------------

def list_clinics() -> List[Clinic]:
    db = SessionLocal()
    try:
        query = text("SELECT coId, coName, coLocation, coSystemType, coSourceFilePattern FROM tbClinic")
        results = db.execute(query).fetchall()
        clinics = []
        for r in results:
            clinics.append(Clinic(id=r[0], name=r[1], location=r[2], system_type=r[3], source_file_pattern=r[4]))
        return clinics
    finally:
        db.close()


def get_clinic_by_id(clinic_id: int) -> Optional[Clinic]:
    db = SessionLocal()
    try:
        query = text("SELECT coId, coName, coLocation, coSystemType, coSourceFilePattern FROM tbClinic WHERE coId = :id")
        r = db.execute(query, {"id": clinic_id}).fetchone()
        if r:
            return Clinic(id=r[0], name=r[1], location=r[2], system_type=r[3], source_file_pattern=r[4])
        return None
    finally:
        db.close()


def get_clinic_by_name(name: str) -> Optional[Clinic]:
    db = SessionLocal()
    try:
        query = text("SELECT coId, coName, coLocation, coSystemType, coSourceFilePattern FROM tbClinic WHERE LOWER(coName) = LOWER(:name)")
        r = db.execute(query, {"name": name}).fetchone()
        if r:
            return Clinic(id=r[0], name=r[1], location=r[2], system_type=r[3], source_file_pattern=r[4])
        return None
    finally:
        db.close()


def save_clinic(clinic: Clinic) -> Clinic:
    db = SessionLocal()
    try:
        # Simplificando para el hackathon: UPSERT manual
        check = db.execute(text("SELECT coId FROM tbClinic WHERE coId = :id"), {"id": clinic.id}).fetchone()
        if check:
            query = text("""
                UPDATE tbClinic 
                SET coName = :name, coLocation = :loc, coSystemType = :sys, coSourceFilePattern = :pat
                WHERE coId = :id
            """)
        else:
            query = text("""
                INSERT INTO tbClinic (coId, coName, coLocation, coSystemType, coSourceFilePattern)
                VALUES (:id, :name, :loc, :sys, :pat)
            """)
        
        db.execute(query, {
            "id": clinic.id,
            "name": clinic.name,
            "loc": clinic.location,
            "sys": clinic.system_type,
            "pat": clinic.source_file_pattern
        })
        db.commit()
        return clinic
    finally:
        db.close()


def next_clinic_id() -> int:
    db = SessionLocal()
    try:
        query = text("SELECT COALESCE(MAX(coId), 0) + 1 FROM tbClinic")
        return db.execute(query).scalar()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Ingestion Job CRUD
# ---------------------------------------------------------------------------

def get_ingestion_job(job_id: str) -> Optional[IngestionJob]:
    return _INGESTION_JOBS.get(job_id)


def save_ingestion_job(job: IngestionJob) -> IngestionJob:
    _INGESTION_JOBS[job.job_id] = job
    return job



# ---------------------------------------------------------------------------
# Staging DB [PostgreSQL]
# ---------------------------------------------------------------------------

from infrastructure.storage.postgres_db import engine

def append_to_staging(table_name: str, df: pd.DataFrame) -> int:
    """Append rows to a staging table in PostgreSQL. Returns the number of rows appended."""
    if df.empty:
        return 0
        
    try:
        # Usamos to_sql de pandas para simplificar la inserción masiva.
        # Postgres usa snake_case/lowercase por defecto para tablas y columnas no citadas,
        # obligamos a lowercase para evitar que pandas cree nuevas tablas citadas o no encuentre columnas.
        df_lower = df.copy()
        df_lower.columns = [str(c).lower() for c in df_lower.columns]
        df_lower.to_sql(table_name.lower(), engine, if_exists='append', index=False)
        return len(df)
    except Exception as e:
        logger.error(f"Error appending to staging table {table_name}: {e}")
        return 0



def get_latest_case_for_patient(patient_id: str) -> Optional[int]:
    """ Finds the most recent CaseId for a given PatientId from tbCaseData. """
    db = SessionLocal()
    try:
        # We try to match coPatientId and pick the one with the latest admission date or highest coId
        query = text("""
            SELECT coId FROM tbCaseData 
            WHERE coPatientId = :pid 
            ORDER BY coAdmission_date DESC NULLS LAST, coId DESC 
            LIMIT 1
        """)
        r = db.execute(query, {"pid": patient_id}).fetchone()
        return r[0] if r else None
    finally:
        db.close()

def get_staging_table(table_name: str) -> Optional[pd.DataFrame]:
    """Retrieves all rows from a staging table in PostgreSQL."""
    try:
        df = pd.read_sql_table(table_name.lower(), engine)
        return df
    except Exception as e:
        print(f"Error reading staging table {table_name}: {e}")
        return None


def upsert_case_data(df: pd.DataFrame):
    """
    Specifically handles tbCaseData upserts.
    Uses coCaseId (or coE2I222 in epaAC) as the key.
    """
    if df.empty:
        return
    
    db = SessionLocal()
    try:
        for _, row in df.iterrows():
            cid = row.get("coCaseId") or row.get("coE2I222")
            if not cid:
                continue
            
            # Check if case exists
            check = db.execute(text("SELECT coId FROM tbCaseData WHERE coCaseId = :cid OR coE2I222 = :cid"), {"cid": cid}).fetchone()
            
            # Convert row to dict and handle NaTs/NaNs for SQL
            data = row.replace({pd.NA: None, pd.NaT: None}).to_dict()
            # Ensure all keys are lowercase for SQL parameters if needed, but we match the schema
            
            if check:
                # Update existing (simplified for hackathon: update common fields)
                update_parts = []
                params = {"cid": cid}
                for k, v in data.items():
                    if k != "coId" and v is not None:
                        update_parts.append(f"{k} = :{k}")
                        params[k] = v
                
                if update_parts:
                    sql = f"UPDATE tbCaseData SET {', '.join(update_parts)} WHERE coCaseId = :cid OR coE2I222 = :cid"
                    db.execute(text(sql), params)
            else:
                # Insert new
                cols = []
                placeholders = []
                params = {}
                for k, v in data.items():
                    if v is not None:
                        cols.append(k)
                        placeholders.append(f":{k}")
                        params[k] = v
                
                if cols:
                    sql = f"INSERT INTO tbCaseData ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
                    db.execute(text(sql), params)
        
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error upserting case data: {e}")

    finally:
        db.close()



def get_staging_summary() -> Dict[str, int]:
    """Counts rows in all known staging tables in PostgreSQL."""
    summary = {}
    db = SessionLocal()
    try:
        for table in STAGING_SCHEMAS.keys():
            count = db.execute(text(f"SELECT COUNT(*) FROM {table.lower()}")).scalar()
            summary[table] = count
        return summary
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Device & Alert Management [NEW]
# ---------------------------------------------------------------------------

def save_device(device: Device) -> Device:
    existing = next((d for d in _DEVICES if d.device_id == device.device_id), None)
    if existing:
        _DEVICES[_DEVICES.index(existing)] = device
    else:
        _DEVICES.append(device)
    
    # Semi-persistence: save to JSON
    _persist_devices()
    return device


def _persist_devices():
    try:
        os.makedirs(os.path.dirname(DEVICES_FILE), exist_ok=True)
        with open(DEVICES_FILE, 'w', encoding='utf-8') as f:
            json.dump([d.to_dict() for d in _DEVICES], f, indent=2)
    except Exception as e:
        print(f"[!] Error persisting devices: {e}")


def load_devices():
    global _DEVICES
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _DEVICES = [Device(**d) for d in data]
        except Exception as e:
            print(f"[!] Error loading devices: {e}")


def get_device(device_id: str) -> Optional[Device]:
    return next((d for d in _DEVICES if d.device_id == device_id), None)


def list_devices(clinic_id: Optional[int] = None) -> List[Device]:
    if clinic_id:
        return [d for d in _DEVICES if d.clinic_id == clinic_id]
    return list(_DEVICES)


def save_alert(alert: Alert) -> Alert:
    _ALERTS.append(alert)
    return alert


def list_alerts(patient_id: Optional[str] = None, limit: int = 50) -> List[Alert]:
    if patient_id:
        return [a for a in _ALERTS if a.patient_id == patient_id][-limit:]
    return _ALERTS[-limit:]


# ---------------------------------------------------------------------------
# Patient & Person Management [NEW]
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Patient & Person Management [NEW - PostgreSQL]
# ---------------------------------------------------------------------------

def get_patient_mapping(clinic_id: int, patient_id: str) -> Optional[Dict[str, Any]]:
    """
    Queries tbPatientMapping in PostgreSQL.
    """
    db = SessionLocal()
    try:
        # Usamos SQL plano para rapidez en el hackathon, o podríamos usar modelos de SQLAlchemy
        query = text("SELECT coClinicId, coPatientId, coPersonId FROM tbPatientMapping WHERE coClinicId = :cid AND coPatientId = :pid")
        result = db.execute(query, {"cid": clinic_id, "pid": patient_id}).fetchone()
        
        if result:
            return {"clinic_id": result[0], "patient_id": result[1], "person_id": result[2]}
            
        # Demo fallback
        if patient_id and patient_id.endswith("42"):
            return {"clinic_id": clinic_id, "patient_id": patient_id, "person_id": 999}
            
        return None
    finally:
        db.close()

def register_patient(clinic_id: int, patient_id: str, details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts into tbPerson and tbPatientMapping in PostgreSQL.
    """
    db = SessionLocal()
    try:
        # 1. Insert Person
        person_query = text("INSERT INTO tbPerson (coFirstName, coLastName, coGender) VALUES (:fn, :ln, :g) RETURNING coId")
        person_id = db.execute(person_query, {
            "fn": details.get("first_name", "Unknown"),
            "ln": details.get("last_name", "Patient"),
            "g": details.get("gender", "U")
        }).fetchone()[0]
        
        # 2. Insert Mapping
        mapping_query = text("INSERT INTO tbPatientMapping (coClinicId, coPatientId, coPersonId) VALUES (:cid, :pid, :perid)")
        db.execute(mapping_query, {"cid": clinic_id, "pid": patient_id, "perid": person_id})
        
        db.commit()
        return {"clinic_id": clinic_id, "patient_id": patient_id, "person_id": person_id, "details": details}
    except Exception as e:
        db.rollback()
        print(f"Error registering patient: {e}")
        raise e
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Alerts [PostgreSQL]
# ---------------------------------------------------------------------------

def save_alert(alert: Alert) -> Alert:
    db = SessionLocal()
    try:
        query = text("""
            INSERT INTO tbalert (coclinicid, copatientid, codeviceid, cotype, coseverity, comessage, cotimestamp, colocation, coscore, costatus, cocaseid)
            VALUES (:cid, :pid, :dev_id, :type, :sev, :msg, :ts, :loc, :score, :status, :case_id)
            RETURNING coid
        """)
        alert_id = db.execute(query, {
            "cid": alert.clinic_id,
            "pid": alert.patient_id,
            "dev_id": alert.device_id,
            "type": alert.type.value if hasattr(alert.type, "value") else str(alert.type),
            "sev": alert.severity,
            "msg": alert.message,
            "ts": alert.timestamp,
            "loc": alert.location,
            "score": alert.impact_g,
            "status": alert.status,
            "case_id": int(alert.case_id) if alert.case_id else None
        }).scalar()
        db.commit()

        alert.id = alert_id
        return alert

    finally:
        db.close()

def list_alerts(patient_id: Optional[str] = None, limit: int = 50) -> List[Alert]:
    db = SessionLocal()
    try:
        if patient_id:
            query = text("SELECT coclinicid, copatientid, codeviceid, cotype, coseverity, comessage, cotimestamp, colocation, coscore, costatus, coid, cocaseid FROM tbalert WHERE copatientid = :pid ORDER BY cotimestamp DESC LIMIT :lim")
            params = {"pid": patient_id, "lim": limit}
        else:
            query = text("SELECT coclinicid, copatientid, codeviceid, cotype, coseverity, comessage, cotimestamp, colocation, coscore, costatus, coid, cocaseid FROM tbalert ORDER BY cotimestamp DESC LIMIT :lim")
            params = {"lim": limit}

            
        results = db.execute(query, params).fetchall()
        alerts = []
        from domain.entities.alert import AlertType
        for r in results:
            alerts.append(Alert(
                clinic_id=r[0],
                patient_id=r[1],
                device_id=r[2],
                type=AlertType(r[3]) if r[3] else AlertType.FALL,
                severity=r[4],
                message=r[5],
                timestamp=r[6].isoformat() if hasattr(r[6], 'isoformat') else str(r[6]),
                location=r[7] or "",
                impact_g=float(r[8] or 0.0),
                status=r[9] or "ACTIVE",
                id=r[10],
                case_id=str(r[11]) if r[11] else None
            ))


        return alerts
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Conversation History [PostgreSQL]
# ---------------------------------------------------------------------------

def get_conversation(conversation_id: str) -> List[Dict[str, str]]:
    db = SessionLocal()
    try:
        query = text("SELECT coHistoryJson FROM tbConversation WHERE coConversationId = :id")
        result = db.execute(query, {"id": conversation_id}).fetchone()
        if result:
            return json.loads(result[0])
        return []
    finally:
        db.close()

def append_to_conversation(conversation_id: str, role: str, content: str, clinic_id: int = 1):
    db = SessionLocal()
    try:
        # Check if conversation exists
        query_check = text("SELECT coHistoryJson FROM tbConversation WHERE coConversationId = :id")
        result = db.execute(query_check, {"id": conversation_id}).fetchone()
        
        if result:
            history = json.loads(result[0])
            history.append({"role": role, "content": content})
            update_query = text("UPDATE tbConversation SET coHistoryJson = :hist, coUpdatedAt = CURRENT_TIMESTAMP WHERE coConversationId = :id")
            db.execute(update_query, {"hist": json.dumps(history), "id": conversation_id})
        else:
            history = [{"role": role, "content": content}]
            insert_query = text("INSERT INTO tbConversation (coConversationId, coClinicId, coHistoryJson) VALUES (:id, :cid, :hist)")
            db.execute(insert_query, {"id": conversation_id, "cid": clinic_id, "hist": json.dumps(history)})
            
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error appending to conversation: {e}")
    finally:
        db.close()

def list_conversations() -> List[str]:
    db = SessionLocal()
    try:
        query = text("SELECT coConversationId FROM tbConversation")
        results = db.execute(query).fetchall()
        return [str(r[0]) for r in results]
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Patient Registration & Lookup [PostgreSQL]
# ---------------------------------------------------------------------------
def get_patient_mapping(clinic_id: int, local_patient_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        query = text("SELECT copersonid FROM tbpatientmapping WHERE coclinicid = :cid AND colocalpatientid = :pid")
        result = db.execute(query, {"cid": clinic_id, "pid": local_patient_id}).fetchone()
        if result:
            return {"person_id": result[0]}
        return None
    finally:
        db.close()

def register_patient(clinic_id: int, local_patient_id: str, details: Dict[str, Any]) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        # Check if mapping already exists
        check_query = text("SELECT coclinicid FROM tbpatientmapping WHERE coclinicid = :cid AND colocalpatientid = :pid")
        if db.execute(check_query, {"cid": clinic_id, "pid": local_patient_id}).fetchone():
            return {"status": "error", "message": "Patient already registered."}

        # Insert Person
        person_query = text("""
            INSERT INTO tbperson (cofirstname, colastname, cogender, codateofbirth)
            VALUES (:fname, :lname, :gender, CAST(:dob AS TIMESTAMP))
            RETURNING coid
        """)
        person_id = db.execute(person_query, {
            "fname": details.get("first_name"),
            "lname": details.get("last_name"),
            "gender": details.get("gender"),
            "dob": details.get("dob") if details.get("dob") else None
        }).scalar()

        # Insert Mapping
        map_query = text("""
            INSERT INTO tbpatientmapping (coclinicid, colocalpatientid, copersonid)
            VALUES (:cid, :local_id, :pid)
        """)
        db.execute(map_query, {
            "cid": clinic_id,
            "local_id": local_patient_id,
            "pid": person_id
        })
        
        db.commit()
        return {"status": "success", "person_id": person_id, "clinic_id": clinic_id, "local_patient_id": local_patient_id}
    except Exception as e:
        db.rollback()
        print(f"Error registering patient: {e}")
        raise e
    finally:
        db.close()

def save_nursing_notes_batch(clinic_id: int, notes: List[Dict[str, Any]]):
    db = SessionLocal()
    try:
        query = text("""
            INSERT INTO tbNursingNote (
                coClinicId, coPatientId, coCaseId, coReportDate, coShift, coWard, 
                coNoteText, coSymptoms, coInterventions, coEvaluation, 
                coPriorityLevel, coIsPriority
            ) VALUES (
                :clinic_id, :patient_id, :case_id, :report_date, :shift, :ward,
                :note_text, :symptoms, :interventions, :evaluation,
                :priority_level, :is_priority
            )
        """)
        for n in notes:
            db.execute(query, {
                "clinic_id": clinic_id,
                "patient_id": n.get("PatientID"),
                "case_id": n.get("CaseID"),
                "report_date": n.get("ReportDate"),
                "shift": n.get("Shift"),
                "ward": n.get("Ward"),
                "note_text": n.get("NursingNote"),
                "symptoms": json.dumps(n.get("Analysis", {}).get("symptoms", [])),
                "interventions": json.dumps(n.get("Analysis", {}).get("interventions", [])),
                "evaluation": n.get("Analysis", {}).get("evaluation"),
                "priority_level": n.get("Analysis", {}).get("priority_level", "Medium"),
                "is_priority": n.get("Analysis", {}).get("is_priority", False)
            })
        db.commit()
    finally:
        db.close()

def list_nursing_history(clinic_id: int, patient_id: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        query = text("""
            SELECT coReportDate, coShift, coWard, coNoteText, coSymptoms, 
                   coInterventions, coEvaluation, coPriorityLevel, coIsPriority
            FROM tbNursingNote
            WHERE coClinicId = :cid AND coPatientId = :pid
            ORDER BY coReportDate DESC
        """)
        results = db.execute(query, {"cid": clinic_id, "pid": patient_id}).fetchall()
        history = []
        for r in results:
            history.append({
                "ReportDate": str(r[0]),
                "Shift": r[1],
                "Ward": r[2],
                "NursingNote": r[3],
                "Analysis": {
                    "symptoms": json.loads(r[4]) if r[4] else [],
                    "interventions": json.loads(r[5]) if r[5] else [],
                    "evaluation": r[6],
                    "priority_level": r[7],
                    "is_priority": r[8]
                }
            })
        return history
    finally:
        db.close()

def update_alert_status(alert_id: int, status: str):
    db = SessionLocal()
    try:
        query = text("UPDATE tbAlert SET coStatus = :status WHERE coId = :id")
        db.execute(query, {"status": status.upper(), "id": alert_id})
        db.commit()
    finally:
        db.close()
