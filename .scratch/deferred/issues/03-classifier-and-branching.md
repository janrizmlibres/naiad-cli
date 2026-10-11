# Branching Workflows and the classifying State

Status: ready
Supersedes the deferral: classification is being built now rather than waiting for queueing.

## Decided

Classification is the first State of the Workflow, not a router Naiad owns (ADR 0005). The Workflow branches at two States and converges on the shared tail:

```
classify ─┬─ grill → review → spec → tickets → implement ─┐
          └─ diagnose ─┬───────────────────────────────→  ├─ pull-request → review-fix → done
                       └─ no-repro ────────────────────┘
```

Declared file order is `classify, diagnose, no-repro, grill, review, spec, tickets, implement, pull-request, review-fix, done` — execution order, short branch first. Three States declare candidates explicitly (`classify`, `diagnose`, `no-repro`); every other successor stays implicit, so the existing feature chain is unchanged. Putting the short branch first means the one State that has to declare a rejoin does it a line from its own head rather than reaching eleven States from the bottom of the file.

Naiad learns nothing new about any Workflow's meaning. A Branching State declares its candidates; everything else keeps the declared order as its expected next.

## The bug branch's shape — resolved, against what this file previously argued

One State. `diagnose` runs `/diagnosing-bugs {task}` end to end, fix included, and announces the shared tail. Its only fork is `no-repro`, a Gate State entered when Phase 1 of the skill cannot build a feedback loop at all; the findings stay verbatim in the session, the human types the missing input, and the agent carries on in the same context.

The earlier draft of this file argued for splitting `diagnose` from `fix` with a reviewed diagnosis Artifact between them. That was rejected on evidence from the skill itself — Phase 5 already writes the regression test before the fix, and Phase 6's post-mortem is explicitly better-informed after it, so the split severs a discipline mid-stride and then reconstructs by hand what not Clearing gives for free. The full argument, including what the Artifact would have had to carry, is **ADR 0008**.

This also settles the instance of the risk in `02-clear-and-artifact-discipline.md` that this file predicted: the pressure to manufacture an Artifact the branch would not otherwise write was the signal that the State boundary was wrong, not a gap to be filled.

## Gate-skipping

`--skip-gates` applies to the declared order only; a Gate State named as a branch candidate is never skipped. Without this, an unattended Run that could not reproduce a bug would be told to open a pull request for a fix built on no diagnosis. See **ADR 0007**.

## What has to change in the engine

- `next_state` returns `tuple[State, ...]` — declared candidates when present, else the single declared-order successor, `()` when nothing follows. Four callers: `decide.py`, `protocol.py` (via `expected_next_state`), `kickoff.py`, and `deviation` itself. Plural is the honest type; a singular and a plural accessor side by side would drift, which is what `transitions.py` exists to prevent.
- Gate-skipping is bypassed when a State declares candidates.
- `deviation` returns `tuple[str, ...]`, empty when the Announcement names any candidate. The Run log's `expected` field stays a single joined string: it is a human-readable diagnostic, `deviations()` only tests for presence, and changing the on-disk shape would strand existing Run logs for nothing.
- `{next_state}` renders the candidates joined; the Protocol's expectation line goes plural. Naming one candidate at a Branching State would bias the agent toward whichever was listed first, in exactly the case where its judgment is the point. The names come from the Workflow; the criterion for choosing between them comes from the Prompt.

## What has to change in the Workflow file

- `classify` first, `clear` unset, Prompt in plain prose — no skill. No existing skill fits (`triage` is an issue-tracker state machine and cannot be model-invoked; `demystify` builds a map the Cleared branch head would discard), and a skill whose body is three sentences is indirection rather than encapsulation. It writes no Artifact: its Announcement is the record, and both branch heads Clear anyway.
- `grill` and `diagnose` both `clear = true`, each interpolating `{task}` itself, so `classify`'s reading of the task never biases the branch head — and `diagnose` in particular forms its hypothesis from evidence rather than inheriting a guess. `run.task` is interpolated into every delivered Prompt, not just kickoff's, so nothing is lost.
- The file's comment that "every Prompt opens with the slash command of the skill it runs" needs amending — the rule is mechanical (Claude Code reads a slash command only at the start of a message), not a requirement that every State runs a skill.

## Known unverified

Two things no test can answer, and both belong in the smoke run: whether `classify`'s prose reliably picks the right branch, and whether the agent announces `no-repro` rather than ploughing on without a feedback loop. `docs/smoke/matt-pocock.md` needs both once the code lands.

Starting a Run at `grill` or `diagnose` skips classification, which needs no code — `--start` already accepts any declared State — but does need documenting as the escape hatch for a human who already knows the answer.
