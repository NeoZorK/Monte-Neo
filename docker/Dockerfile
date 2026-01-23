FROM python:3.11-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY pyproject.toml .
COPY README.md .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy source code
COPY src/ src/
COPY scripts/ scripts/

# Create data directories
RUN mkdir -p data/raw data/processed data/results

# Set environment
ENV PYTHONUNBUFFERED=1
ENV MONTE_NEO_DATA_DIR=/app/data

# Headless mode by default
ENV TERM=xterm-256color

# Entry point
ENTRYPOINT ["python", "-m", "monte_neo"]
CMD ["--help"]
