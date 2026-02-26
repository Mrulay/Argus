"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import datasets, jobs, kpis, projects, reports

settings = get_settings()

app = FastAPI(
    title="Argus — KPI & Advisory Portal",
    version="0.1.0",
    description="LLM-Driven Business KPI & Advisory Portal MVP",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(datasets.router)
app.include_router(kpis.router)
app.include_router(jobs.router)
app.include_router(reports.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
