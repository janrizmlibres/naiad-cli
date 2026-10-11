# Naiad v2 — Branching Workflows and the classifying State

Status: ready-for-agent

## Problem Statement

The Workflow that ships is a straight line, and only one kind of work fits it. The Matt Pocock chain — grill, review, spec, tickets, implement, pull request, review fix — is how a *feature* gets built. A bug is not that shape: there is nothing to grill, no spec to write, no tickets to cut. Anyone with a bug to fix and Naiad in front of them has no Run to start, so the whole class of work Naiad would be most useful for at 2am is the class it cannot take.

Behind that sits a structural gap. Naiad's Workflow format can express one successor per State and no more, so there is no way to say "this phase may end in either of two places". Every mechanism that depends on knowing what comes next — the State interpolated into a Prompt, the expectation injected into a fresh context, and the judgment of whether an Announcement left the path — assumes a single answer. A Workflow that forks cannot be written, and an agent that forked anyway would be recorded as having gone astray for doing the right thing.

There is also nothing that decides which shape a given task is. Today the operator decides, silently, by choosing to start a Run at all; the task description is handed to a chain that has already assumed what kind of work it is. That works while a human types every kickoff and stops working the moment anything else starts Runs.

## Solution

The Workflow gains a fork, and the agent chooses which way to go.

Classification becomes the first State of the Workflow rather than something Naiad owns (ADR 0005). Its Prompt reads the task, looks at the codebase, and announces the head of the appropriate branch — exactly as any other State announces its successor. Choosing a branch is a judgment about the work, and judgments about the work belong to the agent.

The bug branch is a single State running the existing diagnosis discipline end to end: build a feedback loop, reproduce, minimise, hypothesise, instrument, fix with a regression test, clean up. It rejoins the feature branch at the pull request, so both kinds of work finish the same way. Its one fork is the case the discipline itself names — when no feedback loop can be built at all, the Run stops for a human, because a diagnosis without a way to reproduce the bug is a guess.

Underneath, a State may now declare its candidate successors instead of inheriting the next one in the file. What the agent may announce becomes a set that usually happens to have one member. Naiad learns nothing about what any branch means: it reads the candidates, tells the agent all of them, and treats any of them as on-path.

An operator who already knows which kind of work they have starts the Run at the branch head and skips classification entirely — which needs no new mechanism, only saying so.

## User Stories

1. As an operator, I want to start a Run for a bug, so that the class of work I most want done overnight is work Naiad can take.
2. As an operator, I want one Workflow file covering both bugs and features, so that swapping shapes does not mean maintaining two files with a duplicated tail.
3. As an operator, I want the branches to converge on the same pull request and review-fix States, so that a change to how pull requests are opened is made once.
4. As an operator, I want to describe my task in the same words regardless of its kind, so that I do not have to know Naiad's taxonomy before I can use it.
5. As an operator, I want the agent to decide which branch my task belongs to, so that I do not have to classify work I have only just described.
6. As an operator, I want to start a Run directly at a branch head, so that when I already know it is a bug I skip a classification that can only be wrong.
7. As an operator, I want the branch the agent chose recorded, so that a Run that went the wrong way is diagnosable after the fact.
8. As an operator, I want a bug Run to stop and tell me when it cannot reproduce the problem, so that I supply the missing environment or steps rather than receive a fix built on a guess.
9. As an operator, I want that stop to reach me as a notification, so that a Run parked at 3am is something I find in the morning rather than something I discover was never running.
10. As an operator, I want the agent's findings left verbatim in the session when it cannot reproduce, so that I read what it actually tried instead of a summary of it.
11. As an operator, I want to unblock a stuck bug Run by typing into the session, so that I answer in my own words rather than through a fixed command.
12. As an operator, I want the Run to carry on through diagnosis and fix after I have answered, so that my one intervention costs one intervention.
13. As an operator, I want an unattended Run to still stop when it cannot reproduce a bug, so that running unattended never converts "I could not reproduce this" into a pull request.
14. As an operator, I want unattended Runs to keep skipping routine review Gates, so that gaining the safety of story 13 does not cost me the unattended feature.
15. As an operator, I want a bug fix to arrive with a regression test, so that the bug is locked down rather than merely absent today.
16. As an operator, I want the diagnosis discipline run in full rather than truncated, so that the post-mortem and instrumentation cleanup that come after the fix actually happen.
17. As an operator, I want the branch heads to start on a clean context, so that the classifier's reasoning about my task does not become the diagnosis's starting hypothesis.
18. As an operator, I want the task description available to every phase, so that a State that Clears can still say what it is working on.
19. As an operator, I want a Workflow file that reads in the order a Run moves through it, so that I can follow the branch by reading top to bottom.
20. As an operator, I want the existing feature chain unchanged, so that adding a branch does not risk the path that already works.
21. As an operator, I want an unattended bug Run that reproduces successfully to need me for nothing, so that the common case costs me no attention at all.
22. As the agent, I want to be told every State I may announce next, so that I can choose a branch without being nudged toward whichever was listed first.
23. As the agent, I want to be told my candidates again after a Clear, so that a fresh context standing at a fork still knows both its exits.
24. As the agent, I want the criterion for choosing between candidates in the Prompt, so that I know not just what I may announce but when each applies.
25. As the agent, I want announcing any declared candidate to count as staying on the path, so that choosing correctly is not recorded as a mistake.
26. As the agent, I want announcing something outside the candidates still to be permitted, so that a human who redirects me mid-Run is not deadlocked by my obedience.
27. As the agent, I want the task restated when I enter a branch head, so that Clearing the classifier's context costs me nothing I needed.
28. As the agent, I want to stop and report rather than hypothesise when I cannot build a feedback loop, so that I never diagnose a bug I have not seen.
29. As a Workflow author, I want to declare candidate successors on the one or two States that fork, so that expressing a branch does not mean writing a transition graph over every State.
30. As a Workflow author, I want every non-branching State to keep its implicit successor, so that adding a branch does not force me to annotate the whole file.
31. As a Workflow author, I want a candidate naming an undeclared State rejected before the Run starts, so that a typo in a branch fails at load rather than mid-Run.
32. As a Workflow author, I want a Gate State I named as a candidate never to be skipped, so that a stop I put on a fork is one the unattended Run still honours.
33. As a Workflow author, I want a Prompt that runs no skill to be legitimate, so that a three-sentence classifier does not need a skill file to exist.
34. As a maintainer, I want the branch's shape asserted against the file that actually ships, so that the Workflow and its tests cannot drift apart.
35. As a maintainer, I want the expectation to be a plural type throughout, so that a future caller cannot reach for a singular accessor and silently drop a branch.
36. As a maintainer, I want existing Run logs to keep parsing, so that a change to how expectations are computed does not strand the diagnostic record.
37. As a maintainer, I want the rejected alternative shapes recorded, so that the case for splitting diagnosis from fix is not re-derived from scratch in six months.

## Implementation Decisions

### The Workflow's shape

The shipped Workflow becomes eleven States with two forks, converging on the existing tail:

```
classify ─┬─ grill → review → spec → tickets → implement ─┐
          └─ diagnose ─┬───────────────────────────────→  ├─ pull-request → review-fix → done
                       └─ no-repro ────────────────────┘
```

Declared file order is `classify, diagnose, no-repro, grill, review, spec, tickets, implement, pull-request, review-fix, done` — execution order, with the short branch first. Exactly three States declare candidates: `classify` names `grill` and `diagnose`, `diagnose` names `no-repro` and `pull-request`, `no-repro` names `pull-request`. Every other successor stays implicit, so the entire existing feature chain is untouched.

Putting the short branch first is deliberate: one branch must declare an explicit rejoin, and it should be the one where that declaration sits a line from its own head rather than reaching across the whole file.

### The branch resolver

Resolution of "what comes next" becomes plural. A State with declared candidates resolves to those candidates verbatim; a State without them resolves to the single successor the declared order supplies; a State with nothing after it resolves to empty. One resolver, plural return, all callers updated — a singular and a plural accessor side by side would drift, which is the failure the resolver module exists to prevent.

Three consumers change:

- **The delivered Prompt.** The successor interpolated into a Prompt becomes the candidates rendered together. A branching State's Prompt reads "announce `no-repro` or `pull-request`"; the Workflow supplies the names, the Prompt supplies the criterion for choosing.
- **The Protocol.** Its expectation line goes plural — "announce one of: …". Naming a single candidate at a fork would bias the agent toward whichever was listed first, in precisely the case where its judgment is the point. This matters most after a Clear, when the Protocol is the only thing the agent has.
- **Deviation.** An Announcement naming any declared candidate is on-path. Deviation becomes a plural return, empty when the Announcement was expected.

### Gate-skipping and branch candidates (ADR 0007)

Gate-skipping applies to the declared order only. A Gate State named as a candidate is never skipped.

Without this, an unattended Run whose agent could not reproduce a bug would have `no-repro` removed from its expectation and be told to open a pull request — a fix built on no diagnosis, flowing through the shared tail looking like any other Run. The distinction: a Gate State in the declared order is a routine checkpoint an unattended Run may decline, while a Gate State reached as a candidate is a destination the agent chose, and deleting it overrules the judgment ADR 0001 gives away.

A per-State `skippable` flag was rejected — every author would set it identically, so it would encode a rule rather than a choice, and would fail open when forgotten.

This narrows what running with Gates skipped means: not "never stops for a human", but "does not stop for routine checkpoints". It remains affordable because entering a Gate State already notifies, so the cost of not skipping is a notification while the cost of skipping is a wrong fix.

### The bug branch (ADR 0008)

One State, running the diagnosis skill end to end — all six phases, fix and post-mortem included. No separate fix State, and no diagnosis Artifact.

The alternative, argued for in the deferred issue before the skill was read, was to split diagnosis from fix with a reviewed Artifact between them. It was rejected on two grounds. The only honest cut is between instrumentation and fix, but the fix phase already writes its regression test before the fix and then re-runs the original feedback loop, while the post-mortem is explicitly better-informed *after* the fix — so the split severs a discipline mid-stride and then reconstructs by hand, in an Artifact, what not Clearing supplies for free. And the human review the split existed to enable is not wanted: on the path where the hypothesis is confirmed there is no decision for a person to make, and an Artifact with no reader is not carrying meaning between States.

The fork that *is* wanted comes from the skill itself, which instructs the agent to stop and report when it cannot build a feedback loop, and not to hypothesise without one. That becomes `no-repro`: a Gate State with no Prompt and no Artifact. The findings are already in the session verbatim, which is where whoever reads them is looking. The human types the missing input and the agent continues through the remaining phases in the same context.

### Clearing across the fork

Both branch heads Clear, and both interpolate the task themselves. The classifier's reasoning — "this looks like a bug because…" — is a conclusion the branch head has no use for and an active hazard for diagnosis, whose job is to form a hypothesis from evidence rather than inherit a guess.

This is safe by construction rather than by luck: the only thing that must cross the boundary is the task, and Naiad holds that itself and interpolates it into every delivered Prompt, not just the first. That answers, for this branch, the concern recorded in the Clear-and-Artifact-discipline issue.

### The classifying State

Its Prompt is plain prose running no skill. No existing skill fits — the triage skill is an issue-tracker state machine that cannot be model-invoked, and the codebase-tracing skill builds a map the Cleared branch head would discard — and a skill whose entire body is three sentences is indirection rather than encapsulation. The classification criterion exists nowhere else, so putting it in the Prompt creates no second copy of anything.

It writes no Artifact. Its Announcement is the record, the Run log already holds it, and both branch heads Clear.

This makes it the first State whose Prompt does not open with a slash command, so the Workflow file's comment asserting that convention needs amending. The convention's real reason is mechanical — a slash command is only read at the start of a message — not a requirement that every State run a skill.

### The Run log

The recorded expectation stays a single string, rendered by joining the candidates. It is a human-readable diagnostic, the deviations query only tests for presence, and changing the persisted shape would strand existing Run logs for no gain. A deliberate inconsistency — plural in the domain, joined for the record — and commented where it happens.

### Operator surface

Starting a Run at `grill` or `diagnose` skips classification. This needs no code: the start-state option already accepts any declared State name, and ADR 0005 anticipated it. It needs documenting as the escape hatch for an operator who already knows the answer.

## Testing Decisions

A good test here asserts what an operator or an agent actually meets — the Workflow file that ships, the Prompt as delivered, the Protocol as injected, the notification as sent — and never how resolution is computed internally. The change is a type change rippling through three consumers, so the risk is a caller silently dropping a branch, which is only visible in output.

Four seams, all existing. No new seams are introduced.

- **The shipped-Workflow test is the primary seam and the highest available.** It already loads the real file and asserts it as an operator meets it, including gate-skipping behaviour. Everything about the branch's shape belongs here: the three States that declare candidates declare the right ones, the bug branch rejoins at the pull request, the feature chain's implicit successors are unchanged, a branching Prompt renders with both candidates named, kickoff at the classifier and at the diagnosis State produce the right initial Prompts, and the no-reproduction Gate survives gate-skipping where the review Gate does not. That last assertion is ADR 0007 tested against the real Workflow rather than a fixture.
- **The decision-core test.** The pure core (ADR 0004) is the only seam producing the delivered successor string and the Gate-State notification for the no-reproduction stop.
- **The Protocol tests.** The only seam producing the plural expectation line — and the only thing a Cleared agent standing at a fork is told.
- **The transitions test.** Beneath the other three. It gains no new behavioural coverage, but the plural signature forces its existing cases to change, and the candidate-membership rule for Deviation is clearest where the logic lives, given how dense the prior art already is there.

Prior art for all four is the existing test of the same name; each already covers the single-successor case the plural one generalises, and the shipped-Workflow test already asserts a real Workflow's gate-skipping behaviour in exactly the shape the new assertions need.

Work proceeds test-first throughout — Red, then Green, then a named Refactor step with a recorded verdict even when the verdict is to keep what is there. The refactor candidate already anticipated is whether the declared-order walk and the candidate lookup collapse into one resolver.

Two things are explicitly **not** unit-tested, because no test can answer them: whether the classifier reliably picks the right branch, and whether the agent stops at the no-reproduction fork rather than ploughing on without a feedback loop. Both are prompt-quality questions about a real agent, and both belong in the manual smoke document, which the shipped-Workflow test's own docstring already establishes as the boundary.

## Out of Scope

Automatic arrival of Runs — queueing, or anything starting Runs other than a human typing a command. The classifier was originally deferred until this existed; it is being built first, and starting at a branch head remains available to anyone who would rather not use it.

Concurrent Runs. Nothing here should prevent them, and the decision not to introduce a Run-scoped scratch location was made partly on those grounds, but no concurrency work is in this spec.

Any third branch. The mechanism supports one, and the classifier's Prompt would need extending, but only the feature and bug branches are being built.

Enforcement of Clear-and-Artifact discipline in general. This spec resolves the concern for this branch by not Clearing where the context is needed; it does not add the declaration-and-refusal mechanism that issue contemplates.

Splitting diagnosis from fix. Rejected in ADR 0008. If a hard bug ever exhausts the context window before its fix is written, that ADR names the seam to cut at and what the Artifact would have to carry.

Any change to how the pull request or review-fix States behave. They are the shared tail and are inherited unchanged.

Updating the manual smoke document with the new branch. It records observed behaviour of a real agent, so it is written after the code lands and a Run has actually been driven through both branches — not as a prediction alongside the implementation.

## Further Notes

The deferred issue for this work argued a good case for the shape that was ultimately rejected. That case survives in full in ADR 0008 rather than in the issue, so that anyone re-encountering the question finds the argument *and* the evidence against it in the same place. The issue itself was rewritten rather than annotated, because leaving a superseded argument standing invites someone to re-derive it.

The pressure to invent a diagnosis Artifact is worth remembering as a signal in its own right. The Clear-and-Artifact-discipline issue predicted the bug branch would be the first place a Workflow had to manufacture an Artifact it would not otherwise write; it was, and the resolution was that the manufacturing pressure meant the State boundary was in the wrong place, not that the Artifact was missing.

Naiad still knows nothing about what any of these States mean. The glossary gains **Branching State** and amends **Gate State** and **Deviation**, all in Naiad's own vocabulary; the names `classify`, `diagnose` and `no-repro` are one Workflow's language and appear nowhere in the glossary or the engine.
