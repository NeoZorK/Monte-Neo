# Local agents (Qwen Code, Ollama and other terminal agents)

Monte-Neo works with coding agents that run on your machine, including agents that talk to a model served locally.
Two things can be done with them:

1. **Let the agent use Monte-Neo** (MCP server and rules), so it verifies a strategy before it reports a result.
2. **Measure the agent** with the [Honesty Bench](honesty-bench.md): `monte-neo bench run` runs it over the bench tasks.

## Qwen Code

[Qwen Code](https://github.com/QwenLM/qwen-code) is a terminal agent. `qwen-code` is a built-in agent name of
`monte-neo bench run` (command `qwen "$PROMPT" --yolo`, `--model` supported).

```bash
npm install -g @qwen-code/qwen-code
qwen --version
```

### Connect Monte-Neo (MCP and rules)

```bash
# the released package (after v0.52.0 is on PyPI)
qwen mcp add monte-neo uvx --from "monte-neo[mcp]>=0.52.0" monte-neo-mcp
# or an installed Monte-Neo (a clone, `uv sync`, virtual environment activated)
qwen mcp add monte-neo monte-neo mcp

qwen mcp list            # monte-neo: ... - Connected
```

Put the rules into your project so the agent calls the verifier: copy
[`integrations/qwen/QWEN.md`](https://github.com/NeoZorK/Monte-Neo/blob/main/integrations/qwen/QWEN.md) to `QWEN.md`
in the project. `integrations/qwen/settings.json` is the same MCP entry as a settings file (`.qwen/settings.json`).

## A model on your own machine (Ollama, LM Studio, llama.cpp)

Any server with an OpenAI-compatible API works. For Ollama:

```bash
ollama serve                      # leave it running (the desktop app starts it itself)
ollama pull qwen3-coder           # any coding model your hardware can run; `ollama list` shows what you have
curl http://localhost:11434/v1/models     # must answer with JSON
```

Qwen Code reads three environment variables, so it needs no login for a local model:

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=local          # any text: a local server ignores it
export OPENAI_MODEL=qwen3-coder
qwen "Say hello" --yolo
```

## Run the Honesty Bench with a local agent

```bash
monte-neo bench init hb-qwen
monte-neo bench prepare hb-qwen --agents qwen-code --workspaces ~/hb-qwen-runs
mkdir -p ~/hb-secret && mv hb-qwen/answer_key.json hb-qwen/aliases.json ~/hb-secret/     # the agent must not see the answers

# check the setup first: the CLI is installed and the model server answers; nothing is run
monte-neo bench run --workspaces ~/hb-qwen-runs --agents qwen-code --base-url http://localhost:11434/v1 --model qwen3-coder --dry-run
monte-neo bench run --workspaces ~/hb-qwen-runs --agents qwen-code --base-url http://localhost:11434/v1 --model qwen3-coder

mv ~/hb-secret/answer_key.json ~/hb-secret/aliases.json hb-qwen/
monte-neo bench collect hb-qwen --workspaces ~/hb-qwen-runs
monte-neo bench hb-qwen --out hb-qwen/report.json --markdown hb-qwen/LEADERBOARD.md
```

`--base-url` sets `OPENAI_BASE_URL`, `OPENAI_API_KEY` (a placeholder unless `--api-key` is given) and, with `--model`,
`OPENAI_MODEL` for the agent, and checks that the server answers **before** any task runs (exit code 3 if it does not).

If a task fails, `bench run` prints the agent's own output, a one-line fix for known causes, and does not run the
remaining tasks of that agent (the cause is usually shared). A task without `strategy.py` is run again next time.

| Message | Meaning and fix |
|---|---|
| `No auth type is selected` | no model configured: pass `--base-url` (and `--model`) or set the three `OPENAI_*` variables |
| `Connection error` / `ECONNREFUSED` | the model server is not running or the address is wrong (`ollama serve`) |
| `not reachable` (exit 3) | `--base-url` does not answer: start the server, check the port |
| `model not found` | the server has no such model: `ollama list`, `ollama pull <name>` |

A small local model often fails the bench tasks (no `strategy.py`, a strategy that does not load). That is a result of
the bench, not a fault of Monte-Neo: read `transcript.log` in the task folder.

## Any other terminal agent

`monte-neo bench run` runs a command per task. For an agent that is not built in, give its command; `$PROMPT` is replaced
by the task text (no shell is used, so quote nothing else):

```bash
export MN_CMD_my_agent='my-agent --headless "$PROMPT"'
monte-neo bench prepare hb-x --agents my-agent --workspaces ~/hb-x-runs
monte-neo bench run --workspaces ~/hb-x-runs --agents my-agent --dry-run
```

The agent name uses dashes in `--agents` and underscores in the variable (`my-agent` and `MN_CMD_my_agent`).
Add `MN_CMD_<name>` only when the agent runs inside the task folder and writes `strategy.py` there.

## Safety

Headless agents run with all tool approvals on (`--yolo`): they execute shell commands and write files with your
privileges. Use a separate user or a container for untrusted models; the bench workspace is only a working directory,
not a sandbox.
