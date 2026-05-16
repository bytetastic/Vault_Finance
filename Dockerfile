FROM python:3.11-slim

WORKDIR /app

# Tesseract OCR + German language pack + PDF utils
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-deu \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data/documents app/static/uploads

RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8844
CMD ["gunicorn", "--bind", "0.0.0.0:8844", "--workers", "2", "--timeout", "120", "run:app"]
