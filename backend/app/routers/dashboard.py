"""Dashboard spec router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import DashboardSpec
from app.services import database as db

router = APIRouter(prefix="/projects/{project_id}/dashboard", tags=["dashboard"])


@router.get("/latest", response_model=DashboardSpec)
def get_latest_dashboard(project_id: str) -> DashboardSpec:
    items = db.query_by_project("dashboard", project_id)
    if not items:
        raise HTTPException(status_code=404, detail="No dashboard spec found")
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return DashboardSpec(**items[0])
