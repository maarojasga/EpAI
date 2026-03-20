# epAI — Smart Health Data Mapping

**Team COCODE · START Hack 2026 · epaCC Challenge**

epAI is an intelligent healthcare data harmonization platform that automates the mapping of heterogeneous clinical files (CSV, XLSX, PDF, free-text) into a unified relational model. It combines a 3-tier AI column matching engine, 30+ specialized medical data cleaners, real-time telemetry analysis, clinical NLP, and a multilingual patient assistant — all deployable fully offline on-premises.

---

## Frontend

> **Repository:** https://github.com/jeffnmg/epai.git

The React 18 + TypeScript dashboard provides six views: Mapping Studio, Anomaly Center, Executive View, Data Flow Explorer, Patient Companion, and Settings.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  PRESENTATION        React 18 · Tailwind · React Flow   │
├─────────────────────────────────────────────────────────┤
│  APPLICATION         FastAPI REST API                    │
│  ├── Mapping         Upload → Detect → Match → Clean    │
│  ├── Clinical        Nursing NLP · Telemetry Alerts      │
│  ├── Dashboard       Executive Stats · Audit Trail       │
│  └── Patient Asst.   Chat · Lab Interp. · Vision · TTS  │
├─────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE                                          │
│  ├── PostgreSQL 15   Unified schema + staging tables     │
│  ├── Phi-3 Mini      Offline LLM (column mapping, NLP)  │
│  ├── LLaVA 1.5       Offline vision (OCR, doc reading)  │
│  ├── Claude API      Online mode (enhanced reasoning)    │
│  └── Kokoro TTS      Offline multilingual speech         │
└─────────────────────────────────────────────────────────┘
```

## Quick Start (Docker)

```bash
# 1. Clone
git clone <repo-url> && cd epai-backend

# 2. Configure environment
cp .env.example .env
# Edit .env with your DB credentials and optionally ANTHROPIC_API_KEY

# 3. Launch
docker-compose up --build

# 4. Access
# API Docs:  http://localhost:8002/docs
# Health:    http://localhost:8002/
```

The `init.sql` schema runs automatically on first boot via Docker entrypoint.

### Without Docker

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Ensure PostgreSQL is running and .env is configured
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DB_HOST` | Yes | PostgreSQL host (`db` in Docker, `localhost` otherwise) |
| `DB_USER` | Yes | Database user |
| `DB_PASS` | Yes | Database password |
| `DB_NAME` | Yes | Database name |
| `DB_PORT` | No | Database port (default: `5432`) |
| `ANTHROPIC_API_KEY` | No | Enables online mode with Claude API |
| `GEMINI_API_KEY` | No | Fallback for vision if LLaVA unavailable |
| `MODELS_DIR` | No | Path to local GGUF models (default: `./models`) |
| `CATALOG_PATH` | No | Path to epaAC IID-SID-ITEM catalog (default: `data/IID-SID-ITEM.csv`) |

## Offline / Online Modes

epAI supports dual-mode operation, switchable at runtime via API:

```bash
# Switch to online (Claude API)
curl -X POST http://localhost:8002/api/v1/config/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "online"}'

# Switch back to offline (Phi-3 + LLaVA local)
curl -X POST http://localhost:8002/api/v1/config/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "offline"}'
```

**Offline models** (place in `./models/`):
- `phi-3-mini-4k-instruct.gguf` — text/NLP/mapping
- `llava-v1.5-7b-Q4_K.gguf` + `mmproj-model-f16.gguf` — vision/OCR

## Data Pipeline

The core mapping pipeline processes files in 5 stages:

1. **Detect** — Auto-identifies format (CSV/XLSX/PDF), encoding, delimiter, and target staging table via fingerprint scoring.
2. **Map** — 3-tier column matching: Exact → FuzzyWuzzy (≥80%) → LLM interpretation (Phi-3 or Claude). Files with >96% confidence are auto-accepted.
3. **Clean** — 30+ specialized cleaners: ICD-10 codes, German ward names, Swiss date formats, lab flags, medication statuses, epaAC SID resolution, numeric sanitization, bilingual sex normalization.
4. **Validate** — Null checks, clinical range validation, chronology checks, duplicate detection (within file and against DB). Every transformation logged in a Before/After audit trail.
5. **Load** — Inserts into PostgreSQL staging tables, then promotes to unified relational model (tbObservation, tbCondition, tbCareIntervention).

### Deduplication

- **epaAC-Data-1**: keeps the *last* record on duplicates (per challenge spec)
- **All other tables**: keeps the *first* record
- Cross-checks against existing DB records to prevent re-ingestion

### Challenge Datasets Covered

| Source File | Staging Table | Rows | Key Features |
|---|---|---|---|
| `synth_labs_1000_cases.csv` | `tbImportLabsData` | 1,000 | 15 lab params + flags + ranges |
| `synthetic_cases_icd10_ops.csv` | `tbImportIcd10Data` | 50 | Primary + secondary ICD-10 + OPS |
| `synthetic_medication_raw_inpatient.csv` | `tbImportMedicationInpatientData` | 14,553 | ORDER/CHANGE/ADMIN records |
| `synthetic_device_motion_fall_data.csv` | `tbImportDeviceMotionData` | 24,000 | Hourly fall/movement monitoring |
| `synthetic_device_raw_1hz_motion_fall.csv` | `tbImportDevice1HzMotionData` | 108,000 | 1Hz IMU + pressure sensor data |
| `synthetic_nursing_daily_reports.csv` | `tbImportNursingDailyReportsData` | 181 | Free-text NLP pipeline |
| `epaAC-Data-1..5` (CSV + XLSX) | `tbImportEpaAcData` | Variable | 200+ assessment columns |

## API Modules

### Mapping (`/api/v1/mapping/`)
- `POST /upload/{clinic_id}` — Upload file, get AI mapping suggestions
- `POST /approve/{job_id}` — Submit user decisions, load to staging
- `PUT /session/{job_id}/column` — Edit a single column mapping
- `GET /session/{job_id}/stats` — Dashboard metrics for a job

### Clinical (`/api/v1/clinical/`)
- `POST /nursing/upload/{clinic_id}` — Upload nursing CSV/PDF/image with NLP analysis
- `POST /nursing/evolution` — AI summary of patient condition over time
- `GET /nursing/history/{clinic_id}/{patient_id}` — Chronological nursing history

### Telemetry (`/api/v1/telemetry/`)
- `POST /ingest` — Real-time sensor data with fall detection (score-based: accel + movement + pressure + bed occupancy)
- `GET /alerts` — Active clinical alerts (falls, immobility, recovery)
- `POST /devices/map` — Associate devices to beds/locations

### Patient Assistant (`/api/v1/patient-assistant/`)
- `POST /chat` — Multi-turn conversation with medical context enrichment
- `POST /interpret-image` — OCR + AI interpretation of lab results (photo/PDF)
- `GET /interpret-labs/{clinic_id}/{patient_id}` — Plain-language lab explanation
- `POST /speak` — Offline TTS in 5 languages (EN, DE, FR, IT, ES)

### Dashboard (`/api/v1/dashboard/`)
- `GET /executive-stats` — KPIs, quality score, source distribution
- `GET /ingestion/{job_id}/audit` — Normalization Before/After samples
- `GET /ingestion/{job_id}/rejected` — Rejected rows with reasons
- `GET /columns/{table}/metadata` — Column descriptions with epaAC catalog resolution

Full interactive documentation at `http://localhost:8002/docs`.

## Project Structure

```
epai-backend/
├── api/v1/                  # FastAPI routers
│   ├── mapping.py           # File upload & column matching
│   ├── clinical.py          # Nursing NLP & telemetry
│   ├── patient_assistant.py # Chat, vision, TTS
│   ├── dashboard.py         # Executive stats & audit
│   ├── clinics.py           # Clinic CRUD
│   ├── staging.py           # Data preview
│   └── telemetry.py         # Sensor ingestion & alerts
├── application/             # Business logic (use cases)
│   ├── mapping/             # Upload processing, promotion
│   ├── clinical/            # Nursing NLP analysis
│   ├── assistant/           # Patient chat logic
│   └── telemetry/           # Fall detection orchestration
├── domain/                  # Pure entities & interfaces
│   ├── entities/            # Clinic, Alert, Observation, etc.
│   └── interfaces/          # IAnalyzer abstract class
├── infrastructure/          # External integrations
│   ├── mapping_engine/      # Detect, match, clean, validate
│   ├── analyzers/           # Fall pipeline, TTS, vision
│   ├── storage/             # PostgreSQL, in-memory store
│   └── llm_provider.py      # Offline/online mode switching
├── data/                    # Clinical catalogs (IID-SID-ITEM.csv)
├── models/                  # Local GGUF models (gitignored)
├── tests/                   # Unit tests
├── init.sql                 # PostgreSQL schema (auto-runs on startup)
├── docker-compose.yml       # Full stack: PostgreSQL + backend
├── Dockerfile               # Python 3.11-slim container
├── requirements.txt         # Python dependencies
└── main.py                  # FastAPI entry point
```

## Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | FastAPI, Python 3.11, SQLAlchemy, Pandas, FuzzyWuzzy, PyMuPDF |
| **Database** | PostgreSQL 15 (unified schema + 7 staging tables) |
| **AI (Offline)** | Phi-3 Mini 4K (GGUF), LLaVA 1.5 7B (GGUF), Kokoro TTS |
| **AI (Online)** | Claude API (Sonnet) for enhanced reasoning and vision |
| **DevOps** | Docker, Docker Compose, Google Cloud Run |

## Security & Compliance

- All credentials managed via `.env` (gitignored)
- Patient IDs normalized to integer-only format for universal tracking
- Data never leaves the network in offline mode (Phi-3 + LLaVA run locally)
- Full audit trail: every normalization and rejection is logged with justification
- Strict deduplication prevents duplicate clinical records

## Testing

```bash
# Run unit tests
pytest tests/ -v

# Test individual cleaners
pytest tests/test_cleaners.py -v
```

## Postman Collection

Import `EpAI_Postman_Collection.json` for a complete set of API examples organized by module (Admin, Analyst, Clinical, Patient).

---

**Team COCODE — START Hack 2026**
