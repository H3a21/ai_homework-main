import os
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(title="OCR Service", version="1.0.0")

ocr_engine = None
MAX_IMAGE_BYTES = int(os.getenv("OCR_MAX_IMAGE_BYTES", str(10 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _validate_image(filename: str, content: bytes) -> str:
    if not content:
        raise HTTPException(status_code=400, detail="图片文件不能为空")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="图片文件不能超过 10 MB")

    suffix = Path(filename or "image.png").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="仅支持 PNG 和 JPEG 图片")

    is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = content.startswith(b"\xff\xd8\xff")
    if not (is_png or is_jpeg):
        raise HTTPException(status_code=415, detail="文件内容不是有效的 PNG 或 JPEG 图片")
    if suffix == ".png" and not is_png:
        raise HTTPException(status_code=415, detail="图片扩展名与 PNG 文件内容不匹配")
    if suffix in {".jpg", ".jpeg"} and not is_jpeg:
        raise HTTPException(status_code=415, detail="图片扩展名与 JPEG 文件内容不匹配")
    return suffix


def get_ocr():
    global ocr_engine
    if ocr_engine is None:
        from paddleocr import PaddleOCR
        lang = os.getenv("OCR_LANG", "ch")
        use_angle_cls = os.getenv("OCR_USE_ANGLE_CLS", "true").lower() == "true"
        ocr_engine = PaddleOCR(use_angle_cls=use_angle_cls, lang=lang, show_log=False)
    return ocr_engine


@app.on_event("startup")
async def startup():
    get_ocr()


@app.get("/health")
async def health():
    return {"status": "ok", "engine": "paddleocr"}


@app.post("/ocr")
async def ocr(image: UploadFile = File(...)):
    content = await image.read()
    suffix = _validate_image(image.filename or "image.png", content)
    tmp = tempfile.gettempdir()
    tmp_path = os.path.join(tmp, f"{uuid.uuid4().hex}{suffix}")

    with open(tmp_path, "wb") as f:
        f.write(content)

    try:
        engine = get_ocr()
        result = engine.ocr(tmp_path, cls=True)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    lines = []
    if result and result[0]:
        for line in result[0]:
            bbox, (text, confidence) = line
            lines.append({
                "text": text,
                "confidence": round(float(confidence), 4),
                "bbox": [[round(float(p), 2) for p in pt] for pt in bbox],
            })

    full_text = "".join(line["text"] for line in lines)
    return {"text": full_text, "lines": lines, "line_count": len(lines)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("OCR_PORT", "5001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
