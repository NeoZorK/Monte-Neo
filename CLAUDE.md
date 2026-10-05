# Monte-Neo — agent instructions

Development guide: [docs/development/CLAUDE.md](docs/development/CLAUDE.md) · rules: [docs/development/rules.md](docs/development/rules.md).

## Authorship on public repositories (mandatory)

All changes pushed to public repositories are authored by **Rostyslav Shcherbyna** only:

- Git author and committer: `Rostyslav Shcherbyna <63606118+NeoZorK@users.noreply.github.com>`
  (`git config user.name "Rostyslav Shcherbyna"` and `git config user.email "63606118+NeoZorK@users.noreply.github.com"`).
- No AI attribution anywhere: no `Co-Authored-By` trailers naming an AI, no session links,
  no "Generated with ..." footers in commits, PR titles/bodies, PR comments, reviews, issues or release notes.
- Squash-merge commit messages must not carry AI trailers either.
- `.claude/settings.json` disables Claude Code's built-in attribution; do not re-enable it.

## Signed commits

- On the owner's machine, commits are signed locally with the owner's SSH key (`gpg.format ssh`, `user.signingkey`,
  `commit.gpgsign true`, key loaded in `ssh-agent`); nothing else is needed.
- In a cloud or remote session the owner's private key is not available and must never be requested or stored. Commits
  created there (a plain `git push`, or the Git Data API tools) are **unsigned** and show as Unverified; do not claim otherwise.
- The way to get a Verified commit on `main` is Squash and merge on github.com: the merge commit is signed by GitHub.
  To get Verified commits on a branch, re-sign them on the owner's machine (`git commit --amend --no-edit -S`).

## Language and publication (mandatory)

- Public repositories: **English only** (code, comments, docs, issues, PRs, commits).
- Private working files live in `docs/internal/`, `scripts/internal/`, `tests/internal/` (git-ignored). Never commit, push or link them.

## Release cadence

- Releases (feature, patch, security) can be published **at any time**: there is no limit per day.
- Every release needs the owner's explicit approval, and CI must be green on the merged commit.
  Details: [docs/development/rules.md](docs/development/rules.md).
