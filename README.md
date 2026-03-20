# EpAI — Smart Health Data Mapping & Real-Time Monitoring

**EpAI** is a robust, AI-powered healthcare data orchestration platform designed for the **START HACK 2026** challenge. It bridges the gap between fragmented, heterogeneous clinical sources and a unified analytical model, while providing real-time fall detection for inpatient safety.

---

## 🚀 Key Features

### 1. **Intelligent Data Harmonization**
- **AI-Assisted Mapping**: Automatically detects and maps columns from CSV, XLSX, and PDF files into a **Unified Smart Health Schema**.
- **Human-in-the-Loop**: The system calculates confidence scores and provides AI-driven suggestions for human validation.
- **Unstructured Extraction**: Uses Local LLMs (Phi-3) or Gemini API to extract clinical entities (ICD-10, Medications, Lab Results) from nursing reports and unstructured PDFs.

### 2. **Clinical Data Cleaning & Quality**
- **Automatic Sanitization**: Handles encoding issues, special characters (bad data artifacts), and inconsistent date formats.
- **Anomaly Detection**: Validates lab results against reference ranges (e.g., Sodium, Potassium) and clinical logic (e.g., discharge before admission).
- **ICD-10 & OPS Harmonization**: Unified processing for diagnostic and procedural codes, ensuring cross-clinic comparability.

### 3. **Real-Time Telemetry & Fall Detection**
- **1Hz Sensor Processing**: Analyzes raw accelerometer and pressure data to detect free-fall, impact, and immobility.
- **State-based Alerts**: Triggers critical alerts for Falls, Immobility, and Recovery events.
- **Device-to-Location Mapping**: Correlates sensor IDs with room and bed locations for immediate clinical response.

### 4. **Scalable Cloud Deployment**
- **Google Cloud Run**: Fully containerized with Second Generation execution environment for high-performance processing.
- **Offline-Capable AI**: Supports local model execution (Phi-3 Mini-Instruct) via `llama-cpp-python` for privacy and cost efficiency.

---

## 🛠️ Architecture

The system follows **Domain-Driven Design (DDD)** principles:
- **Domain**: Entities (`Observation`, `Alert`, `Clinic`) and core logic (`FallPipelineAnalyzer`).
- **Application**: Use cases for mapping orchestration and telemetry ingestion.
- **Infrastructure**: Storage (in-memory staging), LLM management, and data cleaners.
- **API**: High-performance endpoints built with FastAPI.

---

## 🔄 Workflow

1.  **Ingest**: Upload a file (Clinic 1, 2, 3, 4 formats).
2.  **Map**: Review AI-suggested column mappings.
3.  **Approve**: Validated data is cleaned and pushed to the Staging/Harmonized SQL layer.
4.  **Monitor**: Connect simulated or real devices to the `/telemetry/ingest` endpoint.
5.  **Alert**: Frontend receives JSON events for immediate clinical action.

---

## 🧪 Quick Run: Telemetry Simulation

To test the real-time detection pipeline, use the simulation script:

```bash
# 1. Start the server
python main.py

# 2. Run simulation with clean data
python scripts/simulate_telemetry.py --file "data/Endtestdaten_ohne_Fehler_ einheitliche ID/synthetic_device_raw_1hz_motion_fall.csv"

# 3. Run simulation with noisy (bad) data
python scripts/simulate_telemetry.py --file "data/Endtestdaten_mit_Fehlern_ einheitliche ID/synth_device_raw_1hz_motion_fall.csv"
```

---

## 📄 License
Developed for **START HACK 2026**. Designed to bridge the gap in healthcare interoperability.
