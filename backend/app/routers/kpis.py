"""KPIs router — list, approve/reject, view computed values."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
import pandas as pd

from app.models import KPI, KPIApprovalRequest, KPIStatus, JobMessage, JobStage, Job, JobStatus
from app.services import database as db, queue as q, storage
from app.services.kpi_engine import get_group_label
from app.services.profiler import load_dataframe

router = APIRouter(prefix="/projects/{project_id}/kpis", tags=["kpis"])


@router.get("/", response_model=list[KPI])
def list_kpis(project_id: str) -> list[KPI]:
    items = db.query_by_project("kpi", project_id)
    kpis = [KPI(**item) for item in items]

    needs_labels = any(kpi.plan.group_by for kpi in kpis)
    if not needs_labels:
        return kpis

    datasets = db.query_by_project("dataset", project_id)
    if not datasets:
        return kpis

    frames: list[pd.DataFrame] = []
    for dataset in datasets:
        data = storage.download_file(dataset["s3_key"])
        frames.append(load_dataframe(data, dataset["filename"]))
    if not frames:
        return kpis

    df = pd.concat(frames, ignore_index=True, sort=False)
    updated: list[KPI] = []
    for kpi in kpis:
        if kpi.plan.group_by:
            label = get_group_label(df, kpi.plan)
            updated.append(kpi.model_copy(update={"value_label": label}))
        else:
            updated.append(kpi)
    return updated


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
