"""KPIs router — list, approve/reject, view computed values."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import KPI, KPIApprovalRequest, KPIStatus, JobMessage, JobStage, Job, JobStatus
from app.services import database as db, queue as q

router = APIRouter(prefix="/projects/{project_id}/kpis", tags=["kpis"])


@router.get("/", response_model=list[KPI])
def list_kpis(project_id: str) -> list[KPI]:
    items = db.query_by_project("kpi", project_id)
    return [KPI(**item) for item in items]


@router.get("/{kpi_id}", response_model=KPI)
def get_kpi(project_id: str, kpi_id: str) -> KPI:
    item = db.get_item("kpi", kpi_id)
    if not item or item.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="KPI not found")
    return KPI(**item)


@router.post("/approve", response_model=list[KPI])
def approve_kpis(project_id: str, body: KPIApprovalRequest) -> list[KPI]:
    """Human approval gate — sets each KPI to approved or rejected."""
    updated: list[KPI] = []
    for kpi_id, status in body.approvals.items():
        item = db.get_item("kpi", kpi_id)
        if not item or item.get("project_id") != project_id:
            raise HTTPException(status_code=404, detail=f"KPI {kpi_id} not found")
        db.update_item("kpi", kpi_id, {"status": status.value})
        updated.append(KPI(**{**item, "status": status}))

    # If any KPIs are approved, enqueue computation job
    approved = [k for k in updated if k.status == KPIStatus.approved]
    if approved:
        job = Job(
            project_id=project_id,
            stage=JobStage.compute_kpis,
        )
        db.put_entity("job", job.job_id, project_id, job.model_dump())
        msg = JobMessage(
            job_id=job.job_id,
            project_id=project_id,
            stage=JobStage.compute_kpis,
        )
        q.enqueue_job(msg)

    return updated
