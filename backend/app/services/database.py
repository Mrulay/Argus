"""DynamoDB service — single-table design."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key

from app.config import get_settings


def _get_table():
    settings = get_settings()
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    dynamodb = boto3.resource("dynamodb", **kwargs)
    return dynamodb.Table(settings.dynamodb_table_name)


# Entity prefixes for PK/SK
_PFX = {
    "project": "PROJECT",
    "dataset": "DATASET",
    "kpi": "KPI",
    "job": "JOB",
    "report": "REPORT",
}


def _pk(entity: str, entity_id: str) -> str:
    return f"{_PFX[entity]}#{entity_id}"


def _to_dynamodb(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_to_dynamodb(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_dynamodb(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def put_item(entity: str, entity_id: str, data: dict[str, Any]) -> None:
    table = _get_table()
    item = {"PK": _pk(entity, entity_id), "SK": _pk(entity, entity_id), **_to_dynamodb(data)}
    table.put_item(Item=item)


def get_item(entity: str, entity_id: str) -> Optional[dict[str, Any]]:
    table = _get_table()
    resp = table.get_item(Key={"PK": _pk(entity, entity_id), "SK": _pk(entity, entity_id)})
    return resp.get("Item")


def update_item(entity: str, entity_id: str, updates: dict[str, Any]) -> None:
    table = _get_table()
    updates = _to_dynamodb(updates)
    set_exprs = [f"#{k} = :{k}" for k in updates]
    expr_names = {f"#{k}": k for k in updates}
    expr_values = {f":{k}": v for k, v in updates.items()}
    table.update_item(
        Key={"PK": _pk(entity, entity_id), "SK": _pk(entity, entity_id)},
        UpdateExpression="SET " + ", ".join(set_exprs),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


def query_by_project(entity: str, project_id: str) -> list[dict[str, Any]]:
    """Query items using GSI project_id-entity-index."""
    table = _get_table()
    resp = table.query(
        IndexName="project_id-entity-index",
        KeyConditionExpression=Key("project_id").eq(project_id) & Key("entity_type").eq(entity),
    )
    return resp.get("Items", [])


def put_entity(entity: str, entity_id: str, project_id: str, data: dict[str, Any]) -> None:
    table = _get_table()
    item = {
        "PK": _pk(entity, entity_id),
        "SK": _pk(entity, entity_id),
        "project_id": project_id,
        "entity_type": entity,
        **_to_dynamodb(data),
    }
    table.put_item(Item=item)
