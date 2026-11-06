import httpx

from app.config import settings


async def ocr_image(image_bytes: bytes, filename: str = "image.png") -> dict:
    url = f"{settings.OCR_SERVICE_URL}/ocr"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            files={"image": (filename, image_bytes, "image/png")},
        )
        resp.raise_for_status()
        return resp.json()
