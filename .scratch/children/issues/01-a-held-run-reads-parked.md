# A Held Run reads parked

Status: resolved
Blocked by: None — can start immediately
Spec: `.scratch/children/PRD.md`

## What to build

A Run whose agent used the Hold verb is parked on purpose: no Nudges, no expiry, until a person types into it. The loop records the park against the Announcement together with its Hold count. The status reading that the Queue listing and a Prune's judgment of Orphaned Runs share asks for that park with the Wait count only. The record then looks stale, and a Held Run reads `running`.

Make the status reading ask with the Hold count as well, exactly as the loop writes it. A Held Run, and a Run parked after a Hold (a Hold followed by the usual silence rule), read `parked` in `naiad queue list`. A Prune treats such an Orphaned Run as parked: it takes it, and does not skip it as running.

## Acceptance criteria

- [ ] A test at the Queue-command seam drives a Run into a Hold over real Run files and asserts `naiad queue list` prints `parked`. It is run first and fails, showing `running`, for the expected reason.
- [ ] A Run that was Held and later parked by the silence rule reads `parked`.
- [ ] A Prune takes an Orphaned Run that is parked after a Hold, rather than skipping it as running.
- [ ] Runs that are parked without a Hold, or after a Wait, still read as before. The existing tests stay green.
- [ ] Refactor: candidates considered (e.g. one helper giving both counts to the loop and the status reading) and a verdict recorded.
