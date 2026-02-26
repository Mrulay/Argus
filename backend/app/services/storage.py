"""S3 service — uploads and report artifacts."""
from __future__ import annotations

from typing import Any

import boto3

from app.config import get_settings


def _get_client():
    settings = get_settings()
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("s3", **kwargs)


def upload_file(key: str, body: bytes, content_type: str = "application/octet-stream") -> str:
    settings = get_settings()
    client = _get_client()
    client.put_object(Bucket=settings.s3_bucket_name, Key=key, Body=body, ContentType=content_type)
    return key


def download_file(key: str) -> bytes:
    settings = get_settings()
    client = _get_client()
    resp = client.get_object(Bucket=settings.s3_bucket_name, Key=key)
    return resp["Body"].read()


def generate_presigned_url(key: str, expiry: int = 3600) -> str:
    settings = get_settings()
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key},
        ExpiresIn=expiry,
    )
