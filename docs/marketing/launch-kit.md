# Launch kit

Ready-to-post texts for announcing Monte-Neo. Every number in these texts must come from a real
run; placeholders look like `<…>`. Do not post results from the Honesty Bench until the public
run is complete.

## GitHub repository "About"

- **Description** (Settings → General, or the gear icon next to "About"):
  > Independent verifier for trading strategies written by AI agents and humans: catches look-ahead bias, hidden costs and overfitting. MCP server, CLI, GitHub Action, signed certificates.
- **Website:** `https://neozork.github.io/Monte-Neo/`
- **Topics:** `backtesting`, `trading`, `algorithmic-trading`, `quantitative-finance`,
  `look-ahead-bias`, `overfitting`, `deflated-sharpe-ratio`, `backtest-verification`, `mcp`,
  `mcp-server`, `model-context-protocol`, `claude-code`, `ai-agents`, `llm-tools`, `python`,
  `github-action`, `quant`, `trading-strategies`, `risk-management`, `reproducibility`
- **Social preview** (Settings → General → Social preview): upload
  [`docs/assets/social-preview.png`](../assets/social-preview.png) (1280×640).
- **Include in the home page:** Releases and Packages on; Deployments off.

## Media

- Banner: [`docs/assets/social-preview.png`](../assets/social-preview.png) (1280×640)
- Animated demo: [`docs/assets/demo-verify.gif`](../assets/demo-verify.gif). Attach it to the X thread, LinkedIn and Reddit posts.

## Show HN

**Title:** Show HN: Monte-Neo – catch look-ahead bias in backtests your AI agent writes

**Body:**

> Coding agents are now good at writing trading backtests, and very good at writing ones that
> look profitable. The usual reasons are the same: the code reads future bars (a `shift(-1)`, a
> centred window, a z-score over the whole series), the costs are missing, or the agent tried
> 300 variants and reported the best.
>
> Monte-Neo is an open-source (MIT) verifier that checks the backtest instead of trusting it.
> It re-runs the strategy on truncated data (does the signal at bar t change when later bars are
> removed?), rewrites the future and checks that the past signal stays put, lints the source,
> prices fees and execution delay, and deflates the Sharpe by the number of variants tried. It
> returns PASS / NEEDS_MORE_EVIDENCE / REJECT with next steps the agent can act on, and a
> reproducible certificate you can sign.
>
> It ships as an MCP server (Claude Code plugin, Codex, Gemini CLI, Cursor), a CLI and a GitHub
> Action. The rules are backed by a "Trap Suite" of 40 strategies that are known to lie.
>
> `pip install monte-neo` · https://github.com/NeoZorK/Monte-Neo
>
> I'd love traps it does not catch yet.

## Reddit: r/algotrading

**Title:** I built an open-source checker for look-ahead bias and overfitting in backtests (works with AI coding agents)

**Body:**

> Most "too good to be true" backtests I have seen, mine and AI-generated ones, fail the same
> way: future data leaks into the signal, costs are ignored, or the best of many variants is
> reported as the only one.
>
> Monte-Neo checks a strategy with:
>
> - a truncation probe and a future-perturbation probe (dynamic look-ahead detection);
> - a static lint for `shift(-k)`, `center=True`, `bfill`, `np.gradient`, `mode="same"` convolutions, FFT filters and whole-sample statistics;
> - net return after fees and slippage, the break-even cost, and one- and two-bar execution delay;
> - the Deflated Sharpe ratio, priced by how many variants you tried.
>
> Input: OHLCV plus either a `signal(df)` function or a positions file. Output: a verdict and a
> JSON certificate that anyone can reproduce.
>
> MIT licensed, runs locally: https://github.com/NeoZorK/Monte-Neo
>
> If you have a leak that it misses, please send it as a trap. That is the most useful feedback.

Other subreddits (adapt the first paragraph): r/quant (methodology angle), r/ClaudeAI and
r/ChatGPTCoding (agent angle: "make your agent verify its own backtest"), r/Python (tooling angle).

## X / Twitter thread

1. Your AI agent just told you its trading strategy has a Sharpe of 3. It is probably reading the future. 🧵
2. The three usual culprits: look-ahead (`shift(-1)`, centred windows, whole-series z-scores), missing costs, and reporting the best of 300 tries.
3. Monte-Neo is an open-source verifier for that. It re-runs your strategy on truncated and rewritten data, lints the code, prices costs and delay, and deflates the Sharpe by the number of tries.
4. It plugs into Claude Code, Codex, Gemini CLI and Cursor over MCP, so the agent checks itself before it reports. Every failed check comes with a fix the agent can apply.
5. Certificates are reproducible and can be signed (Ed25519). `pip install monte-neo` → https://github.com/NeoZorK/Monte-Neo

## LinkedIn

> AI coding agents have made backtests cheap. They have not made them honest.
>
> I have released Monte-Neo, an open-source verifier that checks a trading-strategy backtest before
> anyone trusts it: look-ahead bias, trading costs and execution delay, and selection bias
> through the Deflated Sharpe ratio. It works inside coding agents (MCP), in CI (GitHub Action)
> and from the command line, and it issues reproducible, signed certificates.
>
> For prop firms, strategy marketplaces and trading courses it is a first-pass filter before a
> human review.
>
> https://github.com/NeoZorK/Monte-Neo

## Article (dev.to / Medium / personal blog)

Full text: [`article-six-ways.md`](article-six-ways.md), also published at
`https://neozork.github.io/Monte-Neo/marketing/article-six-ways/`. When cross-posting, set that URL
as the canonical link.

### Outline

**Title:** Six ways your AI agent's backtest lies, and how to catch each one

1. The setup: ask an agent for a profitable strategy on random-walk data (no edge exists).
2. `shift(-1)` and friends: how the truncation probe catches them.
3. Whole-sample statistics (z-score, `rank(pct=True)`, `qcut`): the perturbation probe.
4. Signal processing: `np.gradient`, `np.convolve(mode="same")`, FFT filters.
5. Costs: the edge that is smaller than 10 bps.
6. Execution timing: the edge that disappears with one bar of delay.
7. Selection bias: 200 random strategies, the best one, and the Deflated Sharpe.
8. Putting it in the loop: MCP, the Claude Code plugin, the GitHub Action.

Every code sample comes from `tests/traps/strategies/`, so readers can reproduce each result.

## Catalogue and list entries

One-line description used everywhere:

> Monte-Neo: independent verifier for trading-strategy backtests. Detects look-ahead bias, prices costs and delay, deflates Sharpe by trials; returns signed, reproducible certificates.

| Where | How to submit | Entry |
|-------|---------------|-------|
| Official MCP Registry | Done: published on every release | `io.github.NeoZorK/monte-neo` |
| Glama | Sign in at glama.ai with GitHub; the repository has `glama.json`, so you can claim it | automatic |
| PulseMCP | Indexes the official registry; check the listing, or submit the URL on the site | automatic |
| mcp.so | "Submit" on the site, with the GitHub URL | one-line description |
| Smithery | Sign in with GitHub, add the server from the repository | one-line description |
| MCP Market (mcpmarket.com) | Submission form, with the GitHub URL | one-line description |
| awesome-mcp-servers | Pull request to the list, "Finance & Fintech" section | `- [NeoZorK/Monte-Neo](https://github.com/NeoZorK/Monte-Neo) 🐍 🏠 - Verify trading-strategy backtests: look-ahead probes, costs, Deflated Sharpe, signed certificates.` |
| awesome-quant | Pull request, "Python → Backtesting" or "Trading & Backtesting" section | `- [Monte-Neo](https://github.com/NeoZorK/Monte-Neo) - Verifier for backtests: look-ahead bias, costs, Deflated Sharpe, reproducible certificates.` |
| GitHub Marketplace (Action) | When drafting a release, tick "Publish this Action to the GitHub Marketplace" | Category: Testing; Code quality |

## Rules for all posts

- Only claim what a reader can reproduce with the published code.
- Say that it checks methodology, not future profit. It is not investment advice.
- Do not name or compare with other projects by name.
- Answer every comment within a day for the first week after a launch.
