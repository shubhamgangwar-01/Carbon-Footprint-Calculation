# Hugging Face Spaces (Docker SDK) image: FastAPI backend on port 7860
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    REPORTS_DIR=/tmp/reports MPLCONFIGDIR=/tmp/mpl PORT=7860
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY data/processed data/processed
COPY data/metadata data/metadata
COPY data/samples data/samples
COPY backend backend
RUN mkdir -p /tmp/reports /tmp/mpl && chmod -R 777 /tmp/reports /tmp/mpl
# Spaces run containers as user 1000
RUN useradd -m -u 1000 user && chown -R user /app
USER user
WORKDIR /app/backend
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
