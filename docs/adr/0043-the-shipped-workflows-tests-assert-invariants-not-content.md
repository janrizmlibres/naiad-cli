# The shipped Workflow's tests assert invariants, not content

> Amended by ADR 0052.

The shipped Workflow's test file grew alongside the file it asserted: tables mirroring its States, candidates and settings, and Pins of its sentences — the ancestry test's operand order, the classifier's criterion per branch, triage's permitted end statuses — each backed by an ADR. The file is edited frequently, and every edit was also an edit to the tests, whether or not the edit was wrong. A guard that fires on every change guards nothing, and ADR 0041 had already judged that most Pins cost more than they protect.

We decided the test file asserts only invariants any Workflow file must hold, every one derived from the loaded file rather than written out: it loads under its own name, every brace-shaped slot its Prompts write is one the renderer fills, every successor is named in the Prompt that announces it, non-terminal States lead somewhere, no Prompt delivered after a Clear says "you just", and a Run can start at any delivering State — refused without a Subject exactly where the Prompt names one.

## Consequences

The inversions the old Pin assertions caught — operands reversed, a criterion attached to the wrong branch head, a triage pass ending where it started — now surface in review of the file itself or in manual smoke (docs/smoke/matt-pocock.md) rather than in CI. We accept this. If such an inversion ships, restore the one assertion that would have caught it, pinned to its sentence as the old file did, not the mirror tables.

The scan-block parity check is the loss that bites soonest: ADR 0034 duplicates one routing table into two Prompts on purpose, and nothing now fails when the copies drift. Keeping the two identical is the file author's care, flagged in the file's own comments.
