# Security Policy

Monte-Neo verifies strategies that were written by AI agents and humans, and it produces documents
(certificates) that people trust with money. Both parts need care: the verifier **runs code you give
it**, and a certificate is only worth what its signature and reproducibility guarantee.

## Supported versions

| Version | Security fixes |
|---------|----------------|
| Latest release (see [PyPI](https://pypi.org/project/monte-neo/)) | Yes |
| Older releases | No: upgrade to the latest release |

Security fixes are published as soon as they are ready, at any time, as a patch release when possible.
The change log names every security fix.

## Reporting a vulnerability

Please report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/NeoZorK/Monte-Neo/security/advisories/new), or contact the
repository owner directly. Do not open public issues for exploitable bugs, leaked credentials or sensitive
operational details.

Include: the affected version, reproduction steps, the expected impact and, if you have one, a suggested fix.
Reports are read by the maintainer as they come in; please allow a few days for a first answer. Reporters are
credited in the change log unless they prefer not to be.

## Threat model

**Assets**

- The machine and data of the person who runs `monte-neo verify` or the MCP server.
- Signing keys (`--sign`, `--keygen`) and the trust in signed certificates.
- The integrity of released packages and of the GitHub Action.

**Who can attack, and how**

| Actor | Attack | What stops it |
|-------|--------|---------------|
| Author of a strategy file | The strategy runs with the user's rights: read secrets, call the network, write files | Documented as the design ("only verify code you would run"). `--isolate` blocks network, subprocesses, links and file writes outside the temp directory, and removes secrets from the environment. For code you do not trust use the container recipe in [docs/api/verify.md](docs/api/verify.md) (`docker/verify/Dockerfile`, no network, read-only file system). `--isolate` is a guard against careless code, **not a security boundary**: native code (ctypes, C extensions) can bypass Python audit hooks. |
| Author of a certificate (a forger) | Edit a verdict; sign a fake certificate with their own key | The signature covers the whole certificate (canonical JSON, Ed25519). A certificate signed with any key is *intact*; only the issuer's published key tells who signed it, so `--public-key` (or `key=` on the verification page) is needed for a "trusted" result. The verification page never shows a green tick without an expected key. `--recheck` reproduces a certificate from the original data and code. |
| Attacker who controls a file that a tool reads | Malformed certificate or table: crash, memory exhaustion, reading other files | Strict JSON (no duplicate keys, no NaN, depth limit), size limits for every input (`MONTE_NEO_MAX_INPUT_MB`), the public key inside a certificate is never treated as a file name, `.npy` files are never unpickled. |
| Prompt injection into an AI agent that uses the MCP server | The agent is told to verify a hostile strategy or to write over a file | The MCP server has no shell or write tool except `render_report`, which only writes `.html` / `.htm` files. Strategy code runs only when the agent passes a strategy path; run the agent in a sandbox or ask for `isolate=True`. The HTTP transport listens on `127.0.0.1` only (MCP SDK default, with DNS-rebinding protection). |
| Attacker with a link to the verification page | `?cert=` points to a hostile URL; script injection through certificate text | Only `https://` URLs are fetched (15 s, 8 MB limit, no credentials or referrer); all text is inserted with `textContent`; the HTML report is script-free and ships a Content-Security-Policy. |
| Supply-chain attacker | Malicious dependency, tampered Action, tampered release | Runtime dependencies are audited on every push and weekly (`pip-audit`), code is scanned (CodeQL, Bandit), every GitHub Action is pinned to a commit SHA and updated by Dependabot, workflows start read-only, releases are published to PyPI by OIDC trusted publishing (no long-lived token, with build attestations), a CycloneDX SBOM is attached to each release, OpenSSF Scorecard runs weekly. |

**Out of scope**: the correctness of trading results (Monte-Neo checks backtest methodology, not future
profit; it is not investment advice), and attacks that need control of the machine that runs the verifier.

## Secret handling

Do not commit exchange API keys, API secrets, account identifiers, private datasets, signing keys or
generated results that contain sensitive information. Use `.env` locally and keep `.env.example` limited to
safe placeholders. `.gitignore` excludes `*.key` and `*.pem`; `monte-neo verify --keygen` writes the private
key with owner-only permissions and refuses to overwrite an existing key. The GitHub Action writes the signing
key to a temporary file with mode 600 and deletes it after use.
