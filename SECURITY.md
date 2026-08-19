# Security Policy

## Supported Versions

Security fixes are targeted at the default branch.

## Reporting a Vulnerability

Please report vulnerabilities privately through GitHub Security Advisories when available, or contact the repository owner directly. Do not open public issues for exploitable bugs, leaked credentials, or sensitive operational details.

For reports, include:

- affected commit, tag, or release
- clear reproduction steps
- expected impact
- suggested mitigation, if known

## Secret Handling

Do not commit Binance API keys, API secrets, account identifiers, private datasets, or generated trading results that contain sensitive account information. Use `.env` locally and keep `.env.example` limited to safe placeholders.
