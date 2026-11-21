"""``monte-neo`` entry point: dispatch before importing anything heavy.

``verify``, ``alpha``, ``policy``, ``init-ci``, ``bench`` and ``mcp`` load only what they need; ``--version`` loads
nothing. Everything else opens the interactive research CLI (extra ``research``).
"""

from __future__ import annotations

import sys

HELP = """usage: monte-neo <command> [options]

Commands:
  verify   verify a trading-strategy backtest (monte-neo verify --help)
  alpha    does a cross-sectional signal predict returns, and can it be traded? (monte-neo alpha --help)
  hall     Hall of Fame: rank certificates by evidence, medals (monte-neo hall --help)
  policy   write or check your institution's thresholds (monte-neo policy init)
  dossier  turn a certificate into a validation dossier for a committee (monte-neo dossier --demo)
  repair   repair a strategy's defects without overfitting it, or say why not (monte-neo repair --demo)
  readiness the ARL, depth and next steps for one certificate (monte-neo readiness --help)
  research honest strategy search: fixed split, ledger, one sealed holdout (monte-neo research --help)
  catalog  label a strategy by the catalog rules: category, type tag, type mask (monte-neo catalog --help)
  monitor  compare live or paper returns with the backtest; is the alpha dead? (monte-neo monitor --help)
  history  certificate history and diffs; blocks a verdict regression
  register write the hypothesis down before the test
  oracle   hold-out oracle for adaptive search (Thresholdout)
  portfolio verify a set of strategies together
  doctor   known problems of a data provider's export
  discover search for a causal indicator and verify the winner (monte-neo discover --help)
  deploy   forward record of a verified strategy on the Binance spot demo testnet (monte-neo deploy --help)
  registry import a public strategy from the Protocolith registry, try it, deploy it (monte-neo registry --help)
  init-ci  write a GitHub Actions workflow that verifies your strategy (monte-neo init-ci --help)
  bench    Honesty Bench: score agent submissions (monte-neo bench --help)
  mcp      run the MCP server for coding agents (monte-neo mcp --help)

  --version, -V   print the version

Run `monte-neo` without a command to open the interactive research CLI
(needs the extra: pip install 'monte-neo[research]').
"""


def main() -> int:
    """Run ``monte-neo``."""
    from monte_neo._console import ensure_safe_stdio

    ensure_safe_stdio()
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command in ("--version", "-V"):
        from monte_neo._version import __version__

        print(f"monte-neo {__version__}")
        return 0
    if command in ("--help", "-h", "help"):
        print(HELP, end="")
        return 0
    if command == "verify":
        from monte_neo.cli.verify_cmd import main as verify_main

        return verify_main(sys.argv[2:])
    if command == "alpha":
        from monte_neo.cli.alpha_cmd import main as alpha_main

        return alpha_main(sys.argv[2:])
    if command in ("dossier", "monitor", "repair", "readiness", "research", "catalog"):
        from importlib import import_module

        return import_module(f"monte_neo.cli.{command}_cmd").main(sys.argv[2:])
    if command == "hall":
        from monte_neo.cli.hall_cmd import main as hall_main

        return hall_main(sys.argv[2:])
    if command == "policy":
        from monte_neo.cli.policy_cmd import main as policy_main

        return policy_main(sys.argv[2:])
    if command == "discover":
        from monte_neo.cli.discover_cmd import main as discover_main

        return discover_main(sys.argv[2:])
    if command in ("history", "register", "oracle", "portfolio", "doctor"):
        from monte_neo.cli import tools_cmd

        return getattr(tools_cmd, f"{command}_main")(sys.argv[2:])
    if command == "deploy":
        from monte_neo.cli.deploy_cmd import main as deploy_main

        return deploy_main(sys.argv[2:])
    if command == "registry":
        from monte_neo.cli.registry_cmd import main as registry_main

        return registry_main(sys.argv[2:])
    if command == "init-ci":
        from monte_neo.cli.init_ci_cmd import main as init_ci_main

        return init_ci_main(sys.argv[2:])
    if command == "bench":
        from monte_neo.cli.bench_cmd import main as bench_main

        return bench_main(sys.argv[2:])
    if command == "mcp":
        from monte_neo.mcp.server import main as mcp_main

        return mcp_main(sys.argv[2:])
    if command and not command.startswith("-"):
        import difflib

        names = [line.split()[0] for line in HELP.splitlines()[3:] if line.startswith("  ") and not line.startswith("  -")]
        close = difflib.get_close_matches(command, names, n=1)
        hint = f" Did you mean `monte-neo {close[0]}`?" if close else ""
        print(f"monte-neo: unknown command {command!r}.{hint} Run `monte-neo --help` for the list.", file=sys.stderr)
        return 2
    try:
        from monte_neo.cli.app import main as app_main
    except ImportError as exc:
        what = f"unknown command {command!r}. " if command else ""
        print(
            f"{what}The interactive research CLI needs extra packages ({exc.name or exc}): "
            "pip install 'monte-neo[research]'.\n"
            "Commands in the base install: monte-neo verify | alpha | policy | hall | repair | dossier | monitor | readiness | research | catalog | discover | history | register | oracle | portfolio | doctor | deploy | registry | init-ci | bench | mcp | --version (monte-neo --help lists them)",
            file=sys.stderr,
        )
        return 2
    return app_main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
