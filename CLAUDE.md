# Monte-Neo — agent instructions

Development guide: [docs/development/CLAUDE.md](docs/development/CLAUDE.md) · rules: [docs/development/rules.md](docs/development/rules.md).

## Authorship on public repositories (mandatory)

All changes pushed to public repositories are authored by **NeoZorK** only:

- Git author and committer: `NeoZorK <63606118+NeoZorK@users.noreply.github.com>`
  (`git config user.name "NeoZorK"` and `git config user.email "63606118+NeoZorK@users.noreply.github.com"`).
- No AI attribution anywhere: no `Co-Authored-By` trailers naming an AI, no session links,
  no "Generated with ..." footers in commits, PR titles/bodies, PR comments, reviews, issues or release notes.
- Squash-merge commit messages must not carry AI trailers either.
- `.claude/settings.json` disables Claude Code's built-in attribution; do not re-enable it.

## Language and publication (mandatory)

- Public repositories: **English only** (code, comments, docs, issues, PRs, commits).

## Release cadence

- Releases (feature, patch, security) can be published **at any time**: there is no limit per day.
- Every release needs the owner's explicit approval, and CI must be green on the merged commit.
  Details: [docs/development/rules.md](docs/development/rules.md).
