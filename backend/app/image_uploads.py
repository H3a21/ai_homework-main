import re
from pathlib import Path

from fastapi import HTTPException

from app.config import settings


IMAGE_TYPES = {
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}


def validate_image_upload(
    filename: str,
    content_type: str | None,
    content: bytes,
) -> tuple[str, str]:
    if not content:
        raise HTTPException(status_code=400, detail="图片文件不能为空")
    if len(content) > settings.MAX_UPLOAD_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="图片文件不能超过 10 MB")

    suffix = Path(filename or "").suffix.lower()
    expected = IMAGE_TYPES.get(suffix)
    if expected is None:
        raise HTTPException(status_code=415, detail="仅支持 PNG 和 JPEG 图片")

    expected_content_type, signature = expected
    if content_type != expected_content_type:
        raise HTTPException(status_code=415, detail="图片类型与扩展名不匹配")
    if not content.startswith(signature):
        raise HTTPException(status_code=415, detail="图片内容不是有效的 PNG 或 JPEG")

    normalized_suffix = ".jpg" if suffix == ".jpeg" else suffix
    return normalized_suffix, expected_content_type


def validate_owned_image_paths(student_id: int, image_paths: list[str]) -> None:
    if not image_paths:
        raise HTTPException(status_code=400, detail="请至少上传一张作业图片")
    if len(image_paths) > settings.MAX_SUBMISSION_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"每次最多上传 {settings.MAX_SUBMISSION_IMAGES} 张图片",
        )
    if len(set(image_paths)) != len(image_paths):
        raise HTTPException(status_code=400, detail="不能重复提交同一张图片")

    pattern = re.compile(
        rf"^submissions/{student_id}/[0-9a-f]{{32}}\.(?:png|jpg)$"
    )
    if any(pattern.fullmatch(path) is None for path in image_paths):
        raise HTTPException(status_code=403, detail="只能提交本人上传的图片")
