# 22 — First publish to PyPI and post-publish QA

Status: ready-for-human
Mode: HITL
Blocked by: 14, 21
Spec: [PRD](../PRD.md), "Packaging, naming and license" and "Testing Decisions"; research on branch `research/pypi-publishing` (absorbed here before ticket 21 drops it)

**What to build:** `naiad-cli` 0.1.0 on PyPI.

1. On PyPI, register a pending trusted publisher: project `naiad-cli`, the recreated repository, the publish workflow's filename, and environment `pypi`.
2. On GitHub, create the `pypi` environment with the maintainer as required reviewer.
3. Push tag `v0.1.0`, approve the publish job, and confirm the release page.
4. Re-run QA steps 1–5 from ticket 20 with `uv tool install naiad-cli` on a clean machine or user.
5. Write the GitHub release notes for 0.1.0.

- [ ] `uv tool install naiad-cli` installs `naiad`, and the starter Run reaches `done`.
- [ ] The PyPI page shows the README, `MIT AND 0BSD`, and the project URLs.
