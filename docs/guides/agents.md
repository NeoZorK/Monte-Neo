# Use Monte-Neo from coding agents

Monte-Neo ships an MCP server, `monte-neo-mcp`, so Claude Code, Codex, Gemini CLI, Cursor
and any other MCP client can verify a strategy before reporting it.
The server runs locally over stdio and reads files from your project.

Requirements: [uv](https://docs.astral.sh/uv/) (for `uvx`) and Python 3.11+.

## MCP tools

| Tool | Purpose |
|------|---------|
| `verify_strategy` | Full verification, returns a `strategy-verdict/1` certificate |
| `verify_grid` | Runs the parameter search inside the verifier (counts `n_trials`) and adds a walk-forward check |
| `probe_lookahead` | Look-ahead probes only (lint, truncation, perturbation, determinism) |
| `cost_stress` | Break-even cost and returns under 0, 1 and 2 bars of execution delay |
| `recheck_certificate` | Reproduces a certificate from its original data and strategy or signals |
| `check_signature` | Checks a certificate's Ed25519 signature, optionally against the issuer's public key |
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

The plugin includes a `PostToolUse` hook. When Claude writes or edits a Python file
that looks like strategy or backtest code, the hook reminds it to verify before
reporting results. It fires once per file per session and never blocks an edit.

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
uvx monte-neo mcp          # v0.20.0+: the MCP SDK is a default dependency
# older pin: uvx --from "monte-neo[mcp]>=0.18.0" monte-neo-mcp
```

Monte-Neo is published to the official MCP Registry as `io.github.NeoZorK/monte-neo` (`server.json`),
so registry-aware clients can install it by name.

For HTTP clients, add `--transport streamable-http`.

## GitHub Actions

```yaml
- uses: NeoZorK/Monte-Neo@v0.32.0
  with:
    ohlcv: data/btc_1h.csv
    strategy: strategies/momentum.py
    n-trials: "12"
```

The job fails on `REJECT`. To also fail on `NEEDS_MORE_EVIDENCE`, set
`fail-on: NEEDS_MORE_EVIDENCE`. The step summary shows every check. The
`verdict` and `certificate` outputs can feed later steps.

Optional inputs:

- `grid: '{"fast": [10, 20], "slow": [80, 120]}'` runs `verify_grid` instead of a single verification.
- `comment: "true"` posts the verdict as a PR comment and updates the same comment on later runs.
  The job needs the `pull-requests: write` permission.
- `signing-key: ${{ secrets.MONTE_NEO_SIGNING_KEY }}` signs the certificate with Ed25519. The `key-id`
  output and the step summary show which key signed it.
- `upload-certificate: "true"` uploads the certificate as the `monte-neo-certificate` workflow artifact.

### Signing certificates in CI

1. Create a key pair locally: `pip install "monte-neo[sign]"` and `monte-neo verify --keygen ci`.
2. Store the content of `ci.key` as the repository secret `MONTE_NEO_SIGNING_KEY`
   (Settings → Secrets and variables → Actions). Delete the local copy if you do not need it.
3. Publish `ci.pub`, for example in your README. Anyone can then check a certificate from your CI:
   `monte-neo verify --check-signature verdict.json --public-key ci.pub`.

The action writes the key to a temporary file that only the runner user can read, and deletes it
right after signing. Pull requests from forks do not receive repository secrets, so their
certificates are not signed.

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
