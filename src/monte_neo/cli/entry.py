"""``monte-neo`` entry point: dispatch before importing anything heavy.

``verify``, ``bench`` and ``mcp`` load only what they need; ``--version`` loads
nothing. Everything else opens the interactive research CLI (extra ``research``).
"""

from __future__ import annotations

import sys


def main() -> int:
    """Run ``monte-neo``."""
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command in ("--version", "-V"):
        from monte_neo._version import __version__

        print(f"monte-neo {__version__}")
        return 0
    if command == "verify":
        from monte_neo.cli.verify_cmd import main as verify_main

        return verify_main(sys.argv[2:])
    if command == "bench":
        from monte_neo.cli.bench_cmd import main as bench_main

        return bench_main(sys.argv[2:])
    if command == "mcp":
        from monte_neo.mcp.server import main as mcp_main

        return mcp_main(sys.argv[2:])
    try:
        from monte_neo.cli.app import main as app_main
    except ImportError as exc:
        print(
            f"The interactive research CLI needs extra packages ({exc.name or exc}): "
            "pip install 'monte-neo[research]'.\n"
            "Commands in the base install: monte-neo verify | bench | mcp | --version",
            file=sys.stderr,
        )
        return 2
    return app_main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
