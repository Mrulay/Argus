"""Projects router."""
from __future__ import annotations

from typing import Any

import boto3
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models import Project, ProjectCreate
from app.services import database as db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=Project, status_code=201)
def create_project(body: ProjectCreate) -> Project:
    project = Project(name=body.name, business_description=body.business_description)
    db.put_entity("project", project.project_id, project.project_id, project.model_dump())
    return project


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    item = db.get_item("project", project_id)
    if not item:
        raise HTTPException(status_code=404, detail="Project not found")
    return Project(**item)


@router.get("/", response_model=list[Project])
def list_projects() -> list[Project]:
    # Full scan — acceptable for MVP scale
    settings = get_settings()
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    dynamodb = boto3.resource("dynamodb", **kwargs)
    table = dynamodb.Table(settings.dynamodb_table_name)
    resp = table.scan(FilterExpression="entity_type = :et", ExpressionAttributeValues={":et": "project"})
    return [Project(**item) for item in resp.get("Items", [])]

