"""Reports router — retrieve and approve advisory reports."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.models import AdvisoryReport, RecommendationApprovalRequest
from app.services import database as db, storage

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])


@router.get("/latest", response_model=AdvisoryReport)
def get_latest_report(project_id: str) -> AdvisoryReport:
    items = db.query_by_project("report", project_id)
    if not items:
        raise HTTPException(status_code=404, detail="No report found")
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return AdvisoryReport(**items[0])


@router.get("/{report_id}", response_model=AdvisoryReport)
def get_report(project_id: str, report_id: str) -> AdvisoryReport:
    item = db.get_item("report", report_id)
    if not item or item.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Report not found")
    return AdvisoryReport(**item)


@router.post("/{report_id}/approve-recommendations", response_model=AdvisoryReport)
def approve_recommendations(
    project_id: str,
    report_id: str,
    body: RecommendationApprovalRequest,
) -> AdvisoryReport:
    """Human approval gate for recommendations."""
    item = db.get_item("report", report_id)
    if not item or item.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Report not found")

    report = AdvisoryReport(**item)
    recommendations = list(report.recommendations)
    for idx, approved in body.approvals.items():
        if 0 <= idx < len(recommendations):
            recommendations[idx] = recommendations[idx].model_copy(update={"approved": approved})

    report = report.model_copy(update={"recommendations": recommendations})
    db.put_entity("report", report_id, project_id, report.model_dump())
    return report
