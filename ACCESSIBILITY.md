# Accessibility

Monte-Neo should be usable by everyone who verifies strategies, including people who use screen readers, keyboard-only
navigation, high-contrast or reduced-color settings, or who read in a terminal without color. This page states what is
supported today, what is not, and how to report a barrier.

## Supported environments

- **Command line** (`monte-neo`) on macOS, Linux and Windows. Verdicts are always written as words (`PASS`, `REJECT`,
  `NEEDS_MORE_EVIDENCE`), never by color alone. Output is formatted with the `rich` library: when the output is not a
  terminal (a pipe or a file), no escape codes are written, and the `NO_COLOR` environment variable turns colors off
  (some bold text remains). `verify --format json` gives machine-readable output that a screen reader or a script can read
  without any terminal formatting.
- **HTML reports** (`verify --html FILE`): a standalone page with `lang="en"`, a page title, semantic headings and tables,
  a light and a dark theme that follow the system setting (`prefers-color-scheme`), and charts drawn as SVG with
  `role="img"` and a text label.
- **Documentation site** (<https://neozork.github.io/Monte-Neo/>): built with MkDocs Material, which provides keyboard
  navigation, a skip link, light and dark themes and text that scales with the browser zoom.

## Known limitations

- Terminal output uses bold and, unless `NO_COLOR` is set, color. There is no separate plain-text mode flag; use
  `--format json` or redirect the output to a file for text without escape codes.
- Chart labels in HTML reports are short summaries, not full descriptions of the data. The numbers behind each chart are
  in the tables of the same report and in the certificate JSON.
- Some tables in reports and documentation are wide and may need horizontal scrolling on narrow screens or at high zoom.
- We have not run a formal audit with assistive technology, and we have not measured conformance against WCAG. Treat the
  statements above as our intent and our best knowledge, not as a conformance claim.

## Reporting a barrier

If something in the CLI, a report or the documentation is hard or impossible to use, please open an issue with the
[accessibility form](https://github.com/NeoZorK/Monte-Neo/issues/new?template=accessibility.yml). Say what you were
trying to do, which tool or assistive technology you use, and what happened. You do not need to propose a fix.

Reports are read by the maintainer as they come in. We treat accessibility barriers as bugs and fix them in the next release,
or in a patch release when the fix is small.
