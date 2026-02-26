"""Datasets router — file upload and profile retrieval."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.models import Dataset, DatasetProfile
from app.services import database as db, storage

router = APIRouter(prefix="/projects/{project_id}/datasets", tags=["datasets"])


@router.post("/", response_model=Dataset, status_code=201)
async def upload_dataset(
    project_id: str,
    file: UploadFile = File(...),
) -> Dataset:
    # Validate project exists
    if not db.get_item("project", project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    data = await file.read()
    dataset_id = str(uuid.uuid4())
    s3_key = f"uploads/{project_id}/{dataset_id}/{file.filename}"

    storage.upload_file(s3_key, data, file.content_type or "application/octet-stream")

    dataset = Dataset(
        dataset_id=dataset_id,
        project_id=project_id,
        filename=file.filename or "upload",
        s3_key=s3_key,
    )
    db.put_entity("dataset", dataset_id, project_id, dataset.model_dump())
    return dataset


@router.get("/{dataset_id}", response_model=Dataset)
def get_dataset(project_id: str, dataset_id: str) -> Dataset:
    item = db.get_item("dataset", dataset_id)
    if not item or item.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return Dataset(**item)


@router.get("/{dataset_id}/profile", response_model=DatasetProfile)
def get_profile(project_id: str, dataset_id: str) -> DatasetProfile:
    item = db.get_item("dataset", dataset_id)
    if not item or item.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not item.get("profile"):
        raise HTTPException(status_code=404, detail="Profile not yet computed")
    return DatasetProfile(**item["profile"])


@router.get("/{dataset_id}/download-url")
def get_download_url(project_id: str, dataset_id: str) -> dict:
    item = db.get_item("dataset", dataset_id)
    if not item or item.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Dataset not found")
    url = storage.generate_presigned_url(item["s3_key"])
    return {"url": url}
