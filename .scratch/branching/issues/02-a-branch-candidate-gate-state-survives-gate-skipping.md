# A branch candidate Gate State survives gate-skipping

Status: ready-for-agent
Blocked by: 01-a-branching-states-candidates-reach-the-agent
Spec: `.scratch/branching/PRD.md`

## What to build

Gate-skipping applies to the declared order alone. A Gate State a Branching State names as a candidate is never skipped, however the Run was started.

A Run resolving with Gates skipped exists so an unattended Run is not held waiting for a human who is not awake, and it works by passing over any State with no Prompt when it computes what the agent owes next. Branching gives that rule a case it was not written for. A fork whose exit is a Gate State — the agent stopping because it cannot proceed — would have that exit removed from its expectation, and the agent would be told to announce the other candidate instead: the very thing it just decided it could not do. In the shipped Workflow's bug branch that means an unattended Run being told to open a pull request for a fix built on no diagnosis, flowing through the shared tail looking like every other Run.

The distinction the rule rests on: a Gate State in the declared order is a routine checkpoint where a human reviews work that went well, and an unattended Run may reasonably decline that review. A Gate State reached as a branch candidate is not a checkpoint but a destination the agent chose, and judgments about the work belong to the agent (ADR 0001) — Naiad silently deleting an option the agent might take is Naiad overruling exactly the judgment it gave away.

A per-State flag marking which Gates may be skipped was considered and rejected: every author would set it identically, so it would encode a rule rather than a choice, and would fail open whenever someone forgot it. The full argument is ADR 0007.

This narrows what a Run started with Gates skipped means — not "never stops for a human" but "does not stop for routine checkpoints" — and the glossary already says so. It stays affordable because entering a Gate State already notifies the operator, so the cost of not skipping is one notification, while the cost of skipping is a wrong fix nobody asked for.

Still verifiable against a Workflow fixture. The shipped Workflow gains no branch until the next ticket.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] A Run resolving with Gates skipped still steps over a Gate State that sits in the declared order
- [ ] A Run resolving with Gates skipped does not step over a Gate State named as a candidate by a Branching State — the candidate is still offered to the agent
- [ ] Both cases are asserted together, so the two kinds of Gate State cannot later be conflated
- [ ] A Terminal State with no Prompt is still never skipped, as before
- [ ] Announcing a candidate Gate State still notifies the operator that the Run is waiting for them
- [ ] The shipped Workflow's existing gate-skipping behaviour is unchanged
