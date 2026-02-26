"""Async worker — polls SQS and processes background jobs."""
from __future__ import annotations

import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any

from app.models import (
    AdvisoryReport,
    Job,
    JobMessage,
    JobStage,
    JobStatus,
    KPI,
    KPIStatus,
)
from app.services import database as db, queue as q, storage
from app.services import llm, profiler as prof
from app.services.kpi_engine import compute_kpis
from app.services.profiler import load_dataframe

logger = logging.getLogger(__name__)

_RUNNING = True


def _signal_handler(sig, frame):  # noqa: ANN001
    global _RUNNING
    logger.info("Shutdown signal received")
    _RUNNING = False


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# ---------------------------------------------------------------------------
# Stage handlers
# ---------------------------------------------------------------------------

def _handle_profile(job: Job, msg: JobMessage) -> None:
    """Profile dataset and then immediately generate KPI proposals."""
    datasets = db.query_by_project("dataset", msg.project_id)
    if not datasets:
        raise ValueError("No datasets found for project")
    dataset = datasets[0] if not msg.dataset_id else next(
        (d for d in datasets if d["dataset_id"] == msg.dataset_id), datasets[0]
    )

    data = storage.download_file(dataset["s3_key"])
    profile = prof.profile_bytes(data, dataset["filename"])

    db.update_item("dataset", dataset["dataset_id"], {"profile": profile.model_dump()})

    project = db.get_item("project", msg.project_id)
    business_description = project.get("business_description", "") if project else ""

    bm_summary = llm.interpret_business_model(business_description, profile)
    proposals = llm.generate_kpi_proposals(business_description, profile, bm_summary)

    for proposal in proposals:
        kpi = KPI(
            project_id=msg.project_id,
            name=proposal.name,
            description=proposal.description,
            rationale=proposal.rationale,
            formula=proposal.formula,
            plan=proposal.plan,
            target=proposal.target,
            unit=proposal.unit,
            status=KPIStatus.proposed,
        )
        db.put_entity("kpi", kpi.kpi_id, msg.project_id, kpi.model_dump())

    db.update_item("job", job.job_id, {
        "status": JobStatus.awaiting_kpi_approval.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


def _handle_compute_kpis(job: Job, msg: JobMessage) -> None:
    """Compute approved KPIs and then enqueue report generation."""
    kpi_items = db.query_by_project("kpi", msg.project_id)
    approved_kpis = [KPI(**item) for item in kpi_items if item.get("status") == KPIStatus.approved.value]

    if not approved_kpis:
        logger.warning("No approved KPIs for project %s", msg.project_id)
        db.update_item("job", job.job_id, {
            "status": JobStatus.complete.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return

    datasets = db.query_by_project("dataset", msg.project_id)
    if not datasets:
        raise ValueError("No datasets found for project")
    dataset = datasets[0]
    data = storage.download_file(dataset["s3_key"])
    df = load_dataframe(data, dataset["filename"])

    computed = compute_kpis(df, approved_kpis)
    for kpi in computed:
        db.update_item("kpi", kpi.kpi_id, {
            "value": kpi.value,
            "computed_at": kpi.computed_at,
        })

    db.update_item("job", job.job_id, {
        "status": JobStatus.running.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    # Enqueue report generation
    report_job = Job(project_id=msg.project_id, stage=JobStage.generate_report)
    db.put_entity("job", report_job.job_id, msg.project_id, report_job.model_dump())
    q.enqueue_job(JobMessage(
        job_id=report_job.job_id,
        project_id=msg.project_id,
        stage=JobStage.generate_report,
    ))

    db.update_item("job", job.job_id, {
        "status": JobStatus.complete.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


def _handle_generate_report(job: Job, msg: JobMessage) -> None:
    """Generate advisory report from KPI results."""
    kpi_items = db.query_by_project("kpi", msg.project_id)
    computed_kpis = [item for item in kpi_items if item.get("value") is not None]
    kpi_results = [
        {"name": k["name"], "value": k.get("value"), "unit": k.get("unit"), "target": k.get("target")}
        for k in computed_kpis
    ]

    datasets = db.query_by_project("dataset", msg.project_id)
    if not datasets:
        raise ValueError("No datasets found for project")
    dataset = datasets[0]
    data = storage.download_file(dataset["s3_key"])
    profile = prof.profile_bytes(data, dataset["filename"])

    project = db.get_item("project", msg.project_id)
    business_description = project.get("business_description", "") if project else ""

    bm_summary, risks, compliance, forecasts, recommendations = llm.generate_advisory_report(
        business_description=business_description,
        business_model_summary="",
        kpi_results=kpi_results,
        profile=profile,
    )

    report = AdvisoryReport(
        project_id=msg.project_id,
        business_model_summary=bm_summary,
        risks=risks,
        compliance_notes=compliance,
        forecasts=forecasts,
        recommendations=recommendations,
    )

    # Persist report to S3 as JSON artifact
    s3_key = f"reports/{msg.project_id}/{report.report_id}.json"
    storage.upload_file(s3_key, report.model_dump_json().encode(), "application/json")
    report = report.model_copy(update={"s3_key": s3_key})

    db.put_entity("report", report.report_id, msg.project_id, report.model_dump())

    db.update_item("job", job.job_id, {
        "status": JobStatus.complete.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


_STAGE_HANDLERS = {
    JobStage.profile: _handle_profile,
    JobStage.generate_kpis: _handle_profile,  # reuse — profile triggers KPI gen
    JobStage.compute_kpis: _handle_compute_kpis,
    JobStage.generate_report: _handle_generate_report,
}


# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------

def process_message(receipt_handle: str, msg: JobMessage) -> None:
    job_item = db.get_item("job", msg.job_id)
    if not job_item:
        logger.error("Job %s not found in DB", msg.job_id)
        q.delete_job(receipt_handle)
        return

    job = Job(**job_item)
    try:
        db.update_item("job", job.job_id, {
            "status": JobStatus.running.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        handler = _STAGE_HANDLERS.get(msg.stage)
        if handler is None:
            raise ValueError(f"Unknown job stage: {msg.stage}")
        handler(job, msg)
    except Exception as exc:
        logger.exception("Job %s failed: %s", job.job_id, exc)
        db.update_item("job", job.job_id, {
            "status": JobStatus.failed.value,
            "error": str(exc),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    finally:
        q.delete_job(receipt_handle)


def run_worker() -> None:
    logger.info("Worker started — polling SQS")
    while _RUNNING:
        try:
            messages = q.receive_jobs(max_messages=1, wait_seconds=20)
            for receipt_handle, msg in messages:
                process_message(receipt_handle, msg)
        except Exception as exc:
            logger.exception("Error in poll loop: %s", exc)
            time.sleep(5)
    logger.info("Worker stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker()
