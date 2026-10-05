"""``python -m monte_neo`` runs the same command line as ``monte-neo``."""

from monte_neo.cli.entry import main

if __name__ == "__main__":
    raise SystemExit(main())
