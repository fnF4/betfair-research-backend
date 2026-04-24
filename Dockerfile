# Dockerfile for Fly.io deploy (Milan region).
# Keeps the image slim and runs the FastAPI backend from backend/.

FROM python:3.11-slim

# System deps needed by betfairlightweight / pip
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (for Docker layer caching)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source
COPY backend/ /app/

# Persistent data directory (mounted from Fly volume in fly.toml)
ENV BETFAIR_DATA_DIR=/data
RUN mkdir -p /data

# Fly.io passes PORT as env var (defaults to 8080 on their edge).
# We default to 8080 to match Fly's internal_port setting.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8080}"]
