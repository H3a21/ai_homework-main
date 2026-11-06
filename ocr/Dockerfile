FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ocr_server.py .

EXPOSE 5001

ENV OCR_LANG=ch
ENV OCR_USE_ANGLE_CLS=true

CMD ["uvicorn", "ocr_server:app", "--host", "0.0.0.0", "--port", "5001"]
