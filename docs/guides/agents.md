# Use Monte-Neo from coding agents

Monte-Neo ships an MCP server, `monte-neo-mcp`, so Claude Code, Codex, Gemini CLI, Cursor
and any other MCP client can verify a strategy before reporting it.
The server runs locally over stdio and reads files from your project.

Requirements: [uv](https://docs.astral.sh/uv/) (for `uvx`) and Python 3.11+.

## MCP tools

| Tool | Purpose |
|------|---------|
| `verify_strategy` | Full verification, returns a `strategy-verdict/1` certificate |
| `probe_lookahead` | Look-ahead probes only (lint, truncation, perturbation, determinism) |
| `cost_stress` | Break-even cost and returns under 0, 1 and 2 bars of execution delay |
| `verdict_schema` | JSON schema of the certificate |
| `verifier_manifest` | Execution semantics and the check catalogue |

All tools take file paths:

- OHLCV as `.csv` or `.parquet`.
- A strategy `.py` file that defines `signal(df)`, or a positions file.

## Claude Code

Recommended: install the plugin. It bundles the MCP server, the `verify-strategy` skill
and the `/verify` command.

```text
/plugin marketplace add NeoZorK/Monte-Neo
/plugin install monte-neo@monte-neo
```

MCP server only:

```bash
claude mcp add monte-neo -- uvx --from "monte-neo[mcp]>=0.18.0" monte-neo-mcp
```

## Codex (OpenAI)

Append [`integrations/codex/config.toml`](https://github.com/NeoZorK/Monte-Neo/blob/main/integrations/codex/config.toml)
to `~/.codex/config.toml`. Then copy the rules from
[`integrations/codex/AGENTS.md`](https://github.com/NeoZorK/Monte-Neo/blob/main/integrations/codex/AGENTS.md)
into your project's `AGENTS.md`.

## Gemini CLI

Copy `integrations/gemini/` to `~/.gemini/extensions/monte-neo/`. The extension
registers the MCP server and loads `GEMINI.md` as context.

## Cursor

1. Copy `integrations/cursor/mcp.json` to `.cursor/mcp.json` in your project, or merge it
   into your existing `.cursor/mcp.json`.
2. Copy `integrations/cursor/rules/monte-neo-verify.mdc` to `.cursor/rules/`.

## Other MCP clients

Use this stdio command:

```bash
uvx --from "monte-neo[mcp]>=0.18.0" monte-neo-mcp
```

For HTTP clients, add `--transport streamable-http`.

## GitHub Actions

```yaml
- uses: NeoZorK/Monte-Neo@v0.18.0
  with:
    ohlcv: data/btc_1h.csv
    strategy: strategies/momentum.py
    n-trials: "12"
```

The job fails on `REJECT`. To also fail on `NEEDS_MORE_EVIDENCE`, set
`fail-on: NEEDS_MORE_EVIDENCE`. The step summary shows every check. The
`verdict` and `certificate` outputs can feed later steps.

## Writing a strategy file

```python
import numpy as np

def signal(df):
    """Positions per row: +1 long, 0 flat, -1 short. Use only rows <= t for bar t."""
    fast = df["close"].rolling(20).mean()
    slow = df["close"].rolling(80).mean()
    return np.where(fast > slow, 1, 0)
```

- Use pandas and numpy only. The file runs inside the MCP server's environment.
- Do not read files or call the network in `signal()`.
- The file is executed with your permissions.
