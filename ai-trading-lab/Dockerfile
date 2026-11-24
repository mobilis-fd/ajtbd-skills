# Reproducible research container (NOT built/tested in the development session: no Docker daemon available).
FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
# data/ and reports/runs are expected as mounted volumes
ENTRYPOINT ["python", "-m", "src.cli"]
CMD ["--help"]
