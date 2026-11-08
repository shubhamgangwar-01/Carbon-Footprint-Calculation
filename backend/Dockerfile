FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
# the engine reads the processed factor database, samples and metadata from /app/data
COPY data/processed data/processed
COPY data/metadata data/metadata
COPY data/samples data/samples
COPY backend backend
WORKDIR /app/backend
EXPOSE 8000
# migrations run on startup (AUTO_MIGRATE=true); factors are seeded if the table is empty
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
