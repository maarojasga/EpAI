"""
main.py - FastAPI application entry point.

To run:
    uvicorn main:app --port 8001 --reload

Docs: http://localhost:8001/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1 import clinics, mapping, staging, telemetry

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


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "online", "mode": "offline-capable", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
