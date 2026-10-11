# The bug branch is one State, and the diagnosis is not an Artifact

The bug branch runs `/diagnosing-bugs`, a six-phase discipline: build a tight pass/fail signal, reproduce and minimise, hypothesise, instrument, fix with a regression test, clean up and post-mortem. The question was how many States it should be.

The case for splitting it was written down before the skill was read, in `.scratch/deferred/issues/03-classifier-and-branching.md`, and it was a good one. A wrong diagnosis makes every downstream minute worthless, so the highest-leverage thing a human can look at is the diagnosis — and reviewing it is only possible if diagnosis and fix are separate States, with an Artifact between them carrying the finding across a Clear. That mirrors the feature branch, where the one Gate sits before committed effort rather than after it.

We decided against it. The bug branch is one State that runs the skill end to end and announces the shared tail.

Two things settled it, and both came from reading the skill rather than reasoning about it.

The split has no seam that does not cut something. The only honest cut is between Phase 4 and Phase 5, and Phase 5 is *"Fix + regression test"* — it already writes the failing test before the fix, so the discipline the split was meant to impose is inside the half being severed. Phase 5 then re-runs the Phase 1 loop against the original, un-minimised scenario, and Phase 6's post-mortem asks what would have prevented the bug, explicitly *after* the fix because "you have more information now than when you started". A Cleared second State has strictly less of that information than the State that earned it. The Artifact would have had to carry the red-capable command and its output, the minimised repro, the confirmed hypothesis with its evidence, and the `[DEBUG-….]` tag prefix so cleanup could still grep — reconstructing by hand what not Clearing gives for free.

And the review the split existed to enable is not wanted. On the path where the hypothesis is confirmed, there is nothing a human adds; the diagnosis is right and reading it costs a person their evening for no decision. Once the human gate goes, the Artifact has no reader, and an Artifact with no reader is not carrying meaning between States — it is paying the cost of a Clear that nobody asked for.

What the branch does need is the other exit. Phase 1 of the skill has a section headed *"When you genuinely cannot build a loop"*: stop, say so explicitly, list what was tried, and ask for environment access, a captured artifact, or permission to instrument — *"Do not proceed to hypothesise without a loop."* That is a real fork in the work and the one place a human is genuinely required, so it is the branch: `diagnose` declares `no-repro` and `pull-request` as its candidates. `no-repro` is a Gate State with no Prompt and no Artifact — the findings are already in the session, verbatim, which is where whoever reads them is looking. The human supplies what was missing by typing into the session, and the agent carries on through the remaining phases in the same context.

## Consequences

The bug branch is the one branch whose States do not correspond to reviewable artifacts. That is a property of the work: diagnosis is a loop discipline rather than an artifact chain, and forcing it into the feature branch's shape was the mistake, not the asymmetry.

`diagnose` holds an entire investigation in one context, from feedback loop to post-mortem, and nothing Clears inside it. If a hard bug ever exhausts the context window before the fix is written, the remedy is the split rejected here, cut at the Phase 4/5 seam with the Artifact enumerated above. That failure announces itself loudly, so waiting for it costs less than pre-empting it.

`no-repro` is the first Gate State that is a branch candidate rather than a step in the declared order, which is what forced the rule in ADR 0007.

The risk named in `02-clear-and-artifact-discipline.md` — that a branch cannot be Cleared safely unless it is made to produce an Artifact it would not otherwise write — is answered here by not Clearing rather than by manufacturing the Artifact. That issue predicted this branch would be the first concrete instance of the problem. It was; the resolution is that the pressure to invent an Artifact was itself the signal that the State boundary was wrong.
