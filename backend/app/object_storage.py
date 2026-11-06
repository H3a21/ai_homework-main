from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
import mimetypes
import os
from typing import Any
from uuid import uuid4

from fastapi.concurrency import run_in_threadpool

from app.config import settings


@dataclass(frozen=True)
class StoredObject:
    content: bytes
    content_type: str


@lru_cache
def get_minio_client() -> Any:
    try:
        from minio import Minio
    except ImportError as exc:
        raise RuntimeError("MinIO SDK is not installed") from exc

    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def _ensure_bucket(client: Any) -> None:
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


def _put_object(
    client: Any,
    object_name: str,
    content: bytes,
    content_type: str,
) -> None:
    _ensure_bucket(client)
    client.put_object(
        settings.MINIO_BUCKET,
        object_name,
        BytesIO(content),
        len(content),
        content_type=content_type,
    )


async def store_submission_image(
    student_id: int,
    content: bytes,
    suffix: str,
    content_type: str,
) -> str:
    object_name = f"submissions/{student_id}/{uuid4().hex}{suffix}"
    await run_in_threadpool(
        _put_object,
        get_minio_client(),
        object_name,
        content,
        content_type,
    )
    return object_name


def _object_exists(client: Any, object_name: str) -> bool:
    try:
        client.stat_object(settings.MINIO_BUCKET, object_name)
        return True
    except Exception as exc:
        if getattr(exc, "code", "") in {"NoSuchKey", "NoSuchObject"}:
            return False
        raise


async def object_exists(object_name: str) -> bool:
    return await run_in_threadpool(
        _object_exists,
        get_minio_client(),
        object_name,
    )


def _read_object(client: Any, object_name: str) -> StoredObject:
    response = client.get_object(settings.MINIO_BUCKET, object_name)
    try:
        content_type = response.headers.get(
            "content-type", "application/octet-stream"
        )
        return StoredObject(response.read(), content_type)
    finally:
        response.close()
        response.release_conn()


async def read_object(object_name: str) -> StoredObject:
    return await run_in_threadpool(
        _read_object,
        get_minio_client(),
        object_name,
    )


def _read_local_file(path: str) -> StoredObject:
    with open(path, "rb") as file:
        content = file.read()
    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return StoredObject(content, content_type)


async def read_image_source(path: str) -> StoredObject:
    if os.path.isfile(path):
        return await run_in_threadpool(_read_local_file, path)
    return await read_object(path)
