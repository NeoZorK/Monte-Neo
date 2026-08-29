# Installation

## Standard Installation (private gitserver)

```bash
git clone /Users/rostsh/git-server/NeoZorK/Monte-Neo.git
cd Monte-Neo
uv sync
uv run bash scripts/build_native.sh
```

LAN clone:

```bash
git clone ssh://rost@2014/Users/rost/git-server/NeoZorK/Monte-Neo.git
```

## Docker Installation

```bash
docker-compose -f docker/docker-compose.yml up -d
docker-compose -f docker/docker-compose.yml exec monte-neo monte-neo
```

## Requirements

- **Operating System**: macOS (Metal), Linux, or Windows (WSL2)
- **Python**: 3.11+
- **Memory**: 4GB+ recommended for large MC simulations
