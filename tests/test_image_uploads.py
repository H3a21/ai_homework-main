"""Tests for image validation and the authenticated upload endpoint."""

import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.image_uploads import validate_image_upload, validate_owned_image_paths
from app.routers import submissions


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-image"
JPEG_BYTES = b"\xff\xd8\xff" + b"test-image"


def test_validate_image_upload_checks_type_signature_and_owner():
    assert validate_image_upload("answer.png", "image/png", PNG_BYTES) == (
        ".png",
        "image/png",
    )
    assert validate_image_upload("answer.jpeg", "image/jpeg", JPEG_BYTES) == (
        ".jpg",
        "image/jpeg",
    )

    with pytest.raises(HTTPException) as disguised:
        validate_image_upload("answer.png", "image/png", JPEG_BYTES)
    assert disguised.value.status_code == 415

    valid_path = f"submissions/8/{'a' * 32}.png"
    validate_owned_image_paths(8, [valid_path])

    with pytest.raises(HTTPException) as wrong_owner:
        validate_owned_image_paths(9, [valid_path])
    assert wrong_owner.value.status_code == 403

    with pytest.raises(HTTPException) as duplicate:
        validate_owned_image_paths(8, [valid_path, valid_path])
    assert duplicate.value.status_code == 400


def test_upload_submission_image_stores_validated_content(monkeypatch):
    stored = {}

    async def fake_store(student_id, content, suffix, content_type):
        stored.update(
            student_id=student_id,
            content=content,
            suffix=suffix,
            content_type=content_type,
        )
        return f"submissions/{student_id}/{'b' * 32}{suffix}"

    monkeypatch.setattr(submissions, "store_submission_image", fake_store)
    upload = UploadFile(
        BytesIO(PNG_BYTES),
        filename="homework.png",
        headers=Headers({"content-type": "image/png"}),
    )

    async def run():
        result = await submissions.upload_submission_image(
            upload, SimpleNamespace(id=8, role="student")
        )
        assert result["image_path"] == f"submissions/8/{'b' * 32}.png"
        assert result["size"] == len(PNG_BYTES)
        assert stored == {
            "student_id": 8,
            "content": PNG_BYTES,
            "suffix": ".png",
            "content_type": "image/png",
        }

    asyncio.run(run())
