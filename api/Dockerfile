# Build context is the repo root, so tutor_core and sample_data can be copied in:
#   docker build -f api/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

COPY tutor_core /app/tutor_core
RUN pip install --no-cache-dir /app/tutor_core

COPY api /app/api
COPY sample_data /app/sample_data
WORKDIR /app/api

# One worker on purpose: the login lockout counter lives in process memory (see design 3B).
CMD ["uvicorn", "--factory", "app.main:app_factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
