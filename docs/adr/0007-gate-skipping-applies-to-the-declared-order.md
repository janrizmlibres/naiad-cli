# Gate-skipping applies to the declared order, not to branch candidates

A Run started with `--skip-gates` steps over Gate States, so an unattended Run is not held waiting for a human who is not awake. It works by having the expectation resolver pass over any prompt-less State when it computes what the agent owes next.

Branching gives that rule a case it was not written for. The bug branch's `diagnose` State declares two successors: `pull-request` when the cause is found, and `no-repro` — a Gate State — when Phase 1 of `/diagnosing-bugs` cannot build a feedback loop at all. Applied naively, gate-skipping would remove `no-repro` from the expectation, and an unattended agent that could not reproduce the bug would be told, by Naiad, to open a pull request. A fix built on no diagnosis is the worst output this branch can produce, and it would flow through the shared tail looking like any other Run.

We decided that gate-skipping applies to the declared order only. When a State declares candidate successors, the expectation is those candidates verbatim and nothing is skipped. `--skip-gates` continues to step over `review`; it never touches `no-repro`.

The alternative was a per-State `skippable = false` flag, letting the Workflow author mark the ones that must be reached. It was rejected because every author would set it the same way — a Gate State nobody can reach is not a State anyone writes on purpose — so the flag would encode a rule rather than a choice, and would fail open when someone forgot it.

The distinction the rule rests on is this. A Gate State in the declared order is a routine checkpoint: the human reviews work that went well, and an unattended Run may reasonably decline that review. A Gate State reached as a branch candidate is not a checkpoint but a destination the agent chose, and ADR 0001 puts judgments about the work with the agent. Naiad silently deleting an option the agent might have taken is Naiad overruling exactly the judgment it gave away.

## Consequences

`--skip-gates` no longer means "this Run never stops for a human". It means "this Run does not stop for routine checkpoints", and a Run started with it can still park — which is the intended behaviour, not a leak. The glossary says so under **Gate State**, because the option's name suggests the stronger reading and the stronger reading is now wrong.

Parking unattended is not silent. Announcing a Gate State already produces a notification naming the State that is waiting, so a Run that stops on `no-repro` at three in the morning pages someone rather than dying quietly. This is what makes the decision affordable: the cost of not skipping is a notification, while the cost of skipping is a wrong fix nobody asked for.

A Workflow author gets no way to declare a branch candidate that an unattended Run may skip. If that is ever wanted, the `skippable` flag rejected above is the shape it should take, and this ADR is what it has to argue against.
