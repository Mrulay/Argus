"""Jobs router — create and poll job status."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import Job, JobMessage, JobStage, JobStatus
from app.services import database as db, queue as q

router = APIRouter(prefix="/projects/{project_id}/jobs", tags=["jobs"])


@router.post("/", response_model=Job, status_code=201)
def create_job(project_id: str, stage: JobStage, dataset_id: str | None = None) -> Job:
    if not db.get_item("project", project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    job = Job(project_id=project_id, stage=stage)
    db.put_entity("job", job.job_id, project_id, job.model_dump())
    msg = JobMessage(
        job_id=job.job_id,
        project_id=project_id,
        stage=stage,
        dataset_id=dataset_id,
    )
    q.enqueue_job(msg)
    return job


@router.get("/{job_id}", response_model=Job)
def get_job(project_id: str, job_id: str) -> Job:
    item = db.get_item("job", job_id)
    if not item or item.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return Job(**item)


@router.get("/", response_model=list[Job])
def list_jobs(project_id: str) -> list[Job]:
    items = db.query_by_project("job", project_id)
    return [Job(**item) for item in items]
