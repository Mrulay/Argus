"""KPIs router — list, approve/reject, view computed values."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
import pandas as pd

from app.models import (
    KPI,
    KPIApprovalRequest,
    KPIStatus,
    JobMessage,
    JobStage,
    Job,
    JobStatus,
    CustomKPIRequest,
    DatasetProfile,
)
from app.services import database as db, queue as q, storage, llm
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


@router.post("/custom", response_model=KPI, status_code=201)
def create_custom_kpi(project_id: str, body: CustomKPIRequest) -> KPI:
    project = db.get_item("project", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    datasets = db.query_by_project("dataset", project_id)
    if not datasets:
        raise HTTPException(status_code=409, detail="No datasets found for project")

    profiled = next((d for d in datasets if d.get("profile")), None)
    if not profiled:
        raise HTTPException(status_code=409, detail="Dataset profile not ready")

    profile = profiled["profile"]
    viable, reason, proposal = llm.generate_custom_kpi(
        user_request=body.request,
        business_description=project.get("business_description", ""),
        profile=DatasetProfile(**profile),
    )
    if not viable or not proposal:
        raise HTTPException(status_code=422, detail=reason or "Invalid KPI request")

    kpi = KPI(
        project_id=project_id,
        name=proposal.name,
        description=proposal.description,
        rationale=proposal.rationale,
        formula=proposal.formula,
        plan=proposal.plan,
        target=proposal.target,
        unit=proposal.unit,
        status=KPIStatus.proposed,
    )
    db.put_entity("kpi", kpi.kpi_id, project_id, kpi.model_dump())
    return kpi
