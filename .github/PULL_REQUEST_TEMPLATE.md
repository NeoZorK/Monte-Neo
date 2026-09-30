## Summary
-

## Test plan
- [ ] `ruff check .`
- [ ] `pytest tests/unit -W ignore`
- [ ] Docs / version Swiss-clock updated if user-facing

## Self-review (the author re-reads the diff before asking anyone else)
- [ ] I read the whole diff as a stranger would and removed what I would question in someone else's PR
- [ ] Behaviour changes have a test that fails without the change
- [ ] Nothing here reads secrets, opens the network or runs untrusted code without a test that says so
- [ ] Workflows, Dockerfiles, release and signing code: permissions are minimal, actions and images are pinned, installs are hash-locked

## Reviewer wanted
Tick if you would like a second pair of eyes from a contributor: it is fine to ask in a comment.
- [ ] Please review
