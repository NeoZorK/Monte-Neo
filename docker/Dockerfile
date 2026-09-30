FROM python:3.14-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:a7aed3216253ee804de3e2d8afa5073baa1a177335345d43845cd4165e43b711 /uv /uvx /bin/

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration files
COPY pyproject.toml .
COPY README.md .
COPY uv.lock .

# Install dependencies (including dev groups for testing)
RUN uv sync --frozen --no-install-project --all-groups

# Copy source code, docs and tests
COPY src/ src/
COPY scripts/ scripts/
COPY tests/ tests/
COPY docs/ docs/

# Install the project
RUN uv sync --frozen --all-groups

# Create data directories
RUN mkdir -p data/raw data/processed data/results

# Set environment
ENV PYTHONUNBUFFERED=1
ENV MONTE_NEO_DATA_DIR=/app/data
ENV PATH="/app/.venv/bin:$PATH"

# Headless mode by default
ENV TERM=xterm-256color

# Entry point
ENTRYPOINT ["uv", "run", "monte-neo"]
CMD ["--help"]
