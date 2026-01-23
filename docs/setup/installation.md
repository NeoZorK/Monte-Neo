# Installation

## Standard Installation

The recommended way to install Monte-Neo is from source:

```bash
git clone https://github.com/NeoZorK/Monte-Neo.git
cd Monte-Neo
pip install -e .
```

## Docker Installation

For an isolated environment, use Docker:

```bash
# Build the image
docker compose -f docker/docker-compose.yml build

# Run interactive CLI
docker compose -f docker/docker-compose.yml run monte-neo-interactive
```

## Requirements

- **Operating System**: macOS, Linux, or Windows (WSL2 recommended).
- **Python**: 3.11+
- **Memory**: 4GB+ recommended for large MC simulations.
