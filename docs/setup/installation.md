# Installation

## Standard Installation

The recommended way to install Monte-Neo is using `uv`:

```bash
# Clone the repository
git clone https://github.com/NeoZorK/Monte-Neo.git
cd Monte-Neo

# Install dependencies and create environment
uv sync
```

## Docker Installation

For an isolated environment, use Docker:

```bash
# Build and start the container
docker-compose -f docker/docker-compose.yml up -d

# Run interactive CLI
docker-compose -f docker/docker-compose.yml exec monte-neo monte-neo
```

## Requirements

- **Operating System**: macOS, Linux, or Windows (WSL2 recommended).
- **Python**: 3.11+
- **Memory**: 4GB+ recommended for large MC simulations.
