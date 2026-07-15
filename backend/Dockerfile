FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MOSAIC_VIDEOS_DIR=/videos \
    MOSAIC_RUNTIME_DIR=/runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
RUN useradd --system --uid 10001 --create-home mosaic \
    && mkdir -p /runtime \
    && chown -R mosaic:mosaic /runtime

USER mosaic
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
