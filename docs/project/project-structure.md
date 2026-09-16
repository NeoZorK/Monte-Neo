# Project Structure

```bash
Monte-Neo/
├── data/              # Data storage (gitignored)
│   ├── raw/           # Raw Parquet files from Binance
│   ├── processed/     # Processed samples
│   └── results/       # Saved indicator results
├── docker/            # Docker configuration
│   ├── Dockerfile     # Main build file
│   └── docker-compose.yml # Service definitions
├── docs/              # Detailed documentation
├── src/
│   └── monte_neo/     # Main package
│       ├── cli/       # Terminal interface logic
│       ├── core/      # Generation and optimization engine
│       ├── data/      # Download and storage utilities
│       ├── indicators/ # Trading logic templates
│       ├── metrics/    # Performance calculation modules
│       ├── monte_carlo/ # MC simulation methods
│       ├── utils/     # Shared helper functions
│       └── visualization/ # Charts and data display
├── tests/             # Unit, integration and stress tests
├── scripts/           # Standalone utility scripts
├── pyproject.toml     # Project metadata and dependencies
└── uv.lock            # Lockfile for consistent environments
```

See [docs/INDEX.md](../INDEX.md) for a detailed file-by-file description.
