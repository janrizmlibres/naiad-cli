# 15 — Citations restated inline

Status: resolved
Mode: AFK
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12
Spec: [PRD](../PRD.md), "The maintainer's record and the history"; ADR 0054

**What to build:** Every comment and docstring in the package and its tests states its rule inline instead of citing a document the public checkout will not hold: an ADR, `CONTEXT.md`, a ticket, the PRD, `.scratch/`, or `docs/smoke/`. That is about 550 lines today: roughly 200 in domain and runtime, 126 in cli, adapters, hooks and skills, and 218 in tests.

It is a wide mechanical change, but comment-only, so it lands green. Work it in batches (domain and runtime; cli, adapters, hooks and skills; tests), committing per batch. Restate the rule where it adds meaning; drop the pointer where the surrounding text already says it. The shipped-workflow test's docstring loses its pointers to the authoring doc and the smoke doc.

A guard test fails if any `.py` file under the package or the tests cites `ADR`, `CONTEXT.md`, `.scratch`, `PRD` or `docs/smoke`.

- [ ] The guard test passes, and the full suite and mypy pass unchanged.
- [ ] No behaviour change: the diff touches comments and docstrings only.
