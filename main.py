"""
main.py - FastAPI application entry point.

To run:
    uvicorn main:app --port 8001 --reload

Docs: http://localhost:8001/docs
"""
import logging

# Configure logging to show in terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("EpAI")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass 


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from api.v1 import clinics, mapping, staging, telemetry, patient_assistant, clinical, dashboard

app = FastAPI(
    title="EpAI — Smart Health Data Mapping API",
    description=(
        "Automates mapping of heterogeneous healthcare files "
        "into the Unified Smart Health Schema. "
        "Works offline using local Phi-3 model."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api/v1
app.include_router(clinics.router, prefix="/api/v1")
app.include_router(mapping.router, prefix="/api/v1")
app.include_router(staging.router, prefix="/api/v1")
app.include_router(telemetry.router, prefix="/api/v1")
app.include_router(patient_assistant.router, prefix="/api/v1")
app.include_router(clinical.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")



# ---------------------------------------------------------------------------
# Config endpoints — switch between offline and online mode
# ---------------------------------------------------------------------------

class ModeRequest(BaseModel):
    mode: str  # "offline" or "online"


@app.post("/api/v1/config/mode", tags=["Config"])
def set_llm_mode(req: ModeRequest):
    """
    Switch between 'offline' (local Phi-3 + LLaVA) and 'online' (Claude API).
    When switching to 'online', ANTHROPIC_API_KEY must be set in environment.
    """
    from infrastructure.llm_provider import set_mode, get_mode
    try:
        old = get_mode()
        logger.info(f"Requested LLM mode change: {old} -> {req.mode}")
        set_mode(req.mode)
        logger.info(f"Successfully switched LLM mode to {req.mode}")
        return {
            "status": "ok",
            "previous_mode": old,
            "current_mode": req.mode,
            "message": f"Switched from '{old}' to '{req.mode}'"
        }

    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/config/mode", tags=["Config"])
def get_llm_mode():
    """Returns the current LLM mode."""
    from infrastructure.llm_provider import get_mode
    mode = get_mode()
    logger.info(f"Current LLM mode requested: {mode}")
    return {"mode": mode}



@app.get("/", tags=["Health"])
def health_check():
    from infrastructure.llm_provider import get_mode
    return {"status": "online", "llm_mode": get_mode(), "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting EpAI Local Server on http://0.0.0.0:8001")
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)

