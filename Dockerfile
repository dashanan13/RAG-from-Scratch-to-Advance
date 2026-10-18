# Container image for the Shakespeare Evidence Desk API + chat web portal (Stage 11).
# The heavy offline build (ingest -> chunk -> embed -> index) runs in notebooks 01-04;
# this image only serves the online pipeline, so it needs the prebuilt .artifacts and
# an Azure identity mounted at runtime (see docker-compose.yml).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY production/ production/
COPY .env.example ./.env.example

EXPOSE 8000

CMD ["uvicorn", "production.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
