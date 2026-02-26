"""SQS service — job queuing."""
from __future__ import annotations

import json
from typing import Any, Optional

import boto3

from app.config import get_settings
from app.models import JobMessage


def _get_client():
    settings = get_settings()
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("sqs", **kwargs)


def enqueue_job(message: JobMessage) -> str:
    settings = get_settings()
    client = _get_client()
    resp = client.send_message(
        QueueUrl=settings.sqs_queue_url,
        MessageBody=message.model_dump_json(),
    )
    return resp["MessageId"]


def receive_jobs(max_messages: int = 1, wait_seconds: int = 20) -> list[tuple[str, JobMessage]]:
    """Returns list of (receipt_handle, JobMessage) tuples."""
    settings = get_settings()
    client = _get_client()
    resp = client.receive_message(
        QueueUrl=settings.sqs_queue_url,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_seconds,
    )
    results = []
    for msg in resp.get("Messages", []):
        body = json.loads(msg["Body"])
        results.append((msg["ReceiptHandle"], JobMessage(**body)))
    return results


def delete_job(receipt_handle: str) -> None:
    settings = get_settings()
    client = _get_client()
    client.delete_message(
        QueueUrl=settings.sqs_queue_url,
        ReceiptHandle=receipt_handle,
    )
