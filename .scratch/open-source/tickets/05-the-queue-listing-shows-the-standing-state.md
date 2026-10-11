# 05 — The Queue listing shows the Standing State

Status: resolved
Mode: AFK
Blocked by: None — can start immediately
Spec: [PRD](../PRD.md), "The engine"; map ticket [04](../issues/04-the-state-column-in-the-queue-listing.md)

**What to build:** `naiad queue list` prints `id  status  state  repo  branch  task  (run)`. The State column is padded to the longest State name in the listing and has no header row. It shows:
- `-` for a waiting Entry;
- the recorded start State for a Run that has not announced;
- otherwise the latest Announcement's State exactly as recorded, with no mark for a Wait or a Question and no Subject, whether the Run is done or not.

Kickoff and Adoption record the resolved start State's name on the Run: the first declared State when the Entry named none. The Standing State resolver reads that record instead of the Workflow, so the Protocol, the Compaction reminder and the listing give one answer, and a Workflow edited under a live Run changes none of them. A Run with no recorded start and no Announcement shows `-`.

- [ ] Listing a waiting, a freshly started, a parked-at-Gate, and a done Run shows `-`, the start State, the Gate, and the final State respectively.
- [ ] A Run whose announced State was later removed from the Workflow still shows that State.
- [ ] Kickoff and Adoption both record the start State, including when the Entry named none.
- [ ] The Protocol's expectation for a Run that has not announced is unchanged after the Workflow's first State is renamed.
- [ ] Built test-first, Refactor verdict recorded.
