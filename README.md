# EpAI - Intelligent Healthcare Data Mapping (START HACK 2026)

EpAI is a powerful backend solution designed to solve the complexity of medical data fragmentation. It provides automated mapping, clinical auditing, and patient assistance using both Online (Claude API) and Offline (Local LLM) capabilities.

## 🚀 Key Features
- **Intelligent Data Mapping**: Automated CSV/XLSX column matching with 96%+ accuracy threshold.
- **Clinical Auditing**: Persistent ingestion history with "Before/After" normalization tracking.
- **Patient Assistant**: Personalized medical note interpretation and multi-turn chat (Powered by Phi-3, LLaVA, and Kokoro TTS).
- **Case-Centric Architecture**: All data (Labs, Nursing, Telemetry) is anchored to unique clinical cases linked to universal Patient IDs.
- **Offline Capable**: Fully deployable on-premises using local Vision-Language Models (VLM).

## 🛠 Tech Stack
- **Backend**: FastAPI (Python 3.11)
- **Database**: PostgreSQL 15
- **AI/ML**: 
  - LLVM: Phi-3 (Local), Claude 3.5 Sonnet (Online)
  - Vision: LLaVA v1.5
  - TTS: Kokoro-82M
- **DevOps**: Docker & Docker Compose, Cloud Run

## 📦 Quick Start (Docker)
Ensure you have Docker and Docker Compose installed.

1. Clone the repository.
2. Configure your `.env` file (see `.env.example`).
3. Raise the stack:
   ```bash
   docker-compose up --build
   ```
4. Access the API at `http://localhost:8002/docs`.

## 📂 Project Structure
- `api/v1/`: Endpoint definitions (Mapping, Clinical, Assistant, Dashboard).
- `application/`: Business logic and use cases.
- `domain/`: Data entities and domain models.
- `infrastructure/`: External integrations (Postgres, LLM Providers, Vision, TTS).
- `data/`: Clinical catalogs (epaAC) and local persistence.

## 🛡 Security & Compliance
- Environment-based credential management.
- Standardized Patient ID normalization (Integer-only) for universal tracking.
- Strict data integrity rules preventing duplicate or orphan clinical records.

*Powered by EpAI — START HACK 2026* 🚀
