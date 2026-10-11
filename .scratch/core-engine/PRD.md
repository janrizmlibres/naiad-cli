# Naiad v2 — Core Engine

Status: ready-for-agent

## Problem Statement

Driving a multi-phase Claude Code workflow to completion means babysitting it. The Matt Pocock chain — grill-with-docs, to-spec, to-tickets, an implement loop, a PR, a review fix — is a sequence of skill invocations where the human's only real contribution between phases is deciding that the previous phase finished properly and typing the next command. That contribution is small, but it is required at every boundary, so the whole chain runs at the speed of human availability. Work that could run overnight instead runs across a week of interruptions.

Naiad v1 automated this and became the wrong thing. It tracked where each piece of work had got to and decided when it could advance, which meant every edge case of every workflow had to be modelled inside Naiad — gates, checkpoints, chains, holds, resume paths, confirm modes. Roughly 8,800 lines of code and 16,400 lines of tests, and the vocabulary needed to describe it ran to forty-odd terms. Adding a workflow meant teaching Naiad about it. Handling a new edge case meant teaching Naiad about that too. The judgment that mattered — is this spec good enough to build from? — lived in the orchestrator, which is the one place that cannot see the work.

The human also remains a hard dependency in a second way. Any phase that asks a question stops dead until someone answers, so a chain that could otherwise run unattended is punctuated by blocking prompts that nobody is awake for.

## Solution

Naiad drives one Claude Code session through a Workflow without a human at each boundary, by inverting who owns progress.

The agent announces its own State. Naiad reads those Announcements and reacts: it delivers the Prompt the Workflow associates with that State, optionally Clearing the session's context first. It never decides that a phase is finished, because it cannot see the work — the agent can, and the agent says so. An agent that is not satisfied simply does not announce, and the Run waits without Naiad needing any vocabulary for the case.

Questions stop being blocking. Rather than asking a human, the agent announces the Question — its text and every option it was weighing — and an Answerer resolves it in the human's stead. The Answerer settles anything inferable from the repository and its documentation, and escalates anything that is not, because answering a question whose answer is not in the repo is inventing rather than inferring.

Because Naiad understands nothing about any particular Workflow, a Workflow is just a file. Swapping the file swaps the workflow. The human stays in the loop where it counts, at Gate States, and intervenes not through Naiad but by typing directly into the session — the same way they would if they were driving it by hand.

## User Stories

1. As an operator, I want to start a Workflow with a single command, so that I can hand off a whole piece of work rather than a single phase.
2. As an operator, I want the chain to advance without me, so that work started in the evening is finished by morning.
3. As an operator, I want to name the Workflow and describe the task at kickoff, so that the agent knows both the shape of the work and the work itself.
4. As an operator, I want to define a Workflow as a file of States and Prompts, so that changing how work flows does not mean changing Naiad.
5. As an operator, I want a Workflow to invoke my existing skills verbatim, so that I do not maintain a second copy of logic that already lives in a skill.
6. As an operator, I want to run the same Workflow with its Gate States skipped, so that I can choose between a supervised run and an unattended one without maintaining two Workflow files.
7. As an operator, I want to start a Run at a State other than the first, so that I can resume or skip a phase whose output I already have.
8. As an operator, I want to be notified when the Run needs me, so that I do not have to watch it.
9. As an operator, I want to be told when the Run finishes, so that I know to review the result.
10. As an operator, I want the Run to stop and wait at a Gate State, so that I can review the agent's work before it builds on it.
11. As an operator, I want to review at a Gate State by reading an Artifact, so that I am judging a document rather than scrolling a transcript.
12. As an operator, I want to release a Gate by typing into the session directly, so that I can approve, redirect, or correct in one action instead of choosing between fixed commands.
13. As an operator, I want to intervene mid-phase by typing into the session, so that anything the design did not anticipate is still recoverable without a Naiad feature for it.
14. As an operator, I want my ad-hoc instruction to be able to send the agent to an earlier State, so that discovering a problem late does not deadlock the Run.
15. As an operator, I want every Question the Answerer resolved recorded with its options and the answer chosen, so that I can audit an unattended run's judgment rather than trusting it.
16. As an operator, I want the Answer log written by Naiad rather than the agent, so that a question cannot go unlogged because the agent forgot.
17. As an operator, I want the Answerer to escalate decisions that are not the repository's to make, so that it never invents a vendor, a budget, or a priority.
18. As an operator, I want the Answerer to remember its earlier answers within a Run, so that its later answers do not contradict its earlier ones.
19. As an operator, I want the Answerer to know the repository, so that its answers reflect the conventions actually in use rather than generic good practice.
20. As an operator, I want a Run's files kept outside the target repository, so that nothing Naiad owns can be committed into a pull request.
21. As an operator, I want a Run's files to survive the work being cleaned up, so that I can inspect what happened after the fact.
22. As an operator, I want the session left alive when a Run ends, so that I can inspect what the agent actually did.
23. As an operator, I want to see when a Run departed from the expected path, so that a confused agent leaves a trace rather than silently producing a strange result.
24. As an operator, I want the Run to recover from the agent simply forgetting to announce, so that a trivial slip does not cost me a night.
25. As an operator, I want recovery attempts to stop after two, so that a genuinely stuck Run stops rather than burning tokens until morning.
26. As an operator, I want to be notified once when the Run needs me rather than on every tick, so that being needed at 3am is one notification and not hundreds.
27. As an operator, I want a hung session to eventually give up, so that a Run that will never produce a signal does not wait forever.
28. As an operator, I want every abnormal outcome to end the same way — notified and waiting for me — so that there is one thing to understand rather than a taxonomy.
29. As an operator, I want a Run that needs me to stay alive rather than exit, so that my typing into the session revives it instead of requiring a restart.
30. As an operator, I want Naiad to stop watching once a Run reaches its Terminal State, so that a finished Run does not leave something ticking forever.
31. As an operator, I want sessions started in bypass permissions mode, so that an unattended Run is never blocked by a permission prompt.
32. As the agent, I want to announce my State with a single command, so that I do not have to maintain a counter and a file format correctly.
33. As the agent, I want an unknown State name rejected with an error naming the valid ones, so that I can correct a typo myself instead of stalling silently.
34. As the agent, I want to be told my expected next State, so that I can announce it without knowing the Workflow.
35. As the agent, I want to announce the same State repeatedly, so that I can work through a list of tickets one cleared session at a time.
36. As the agent, I want to ask a Question through a command, so that I can raise something I cannot decide without waiting for a human who is not there.
37. As the agent, I want to supply the options I was weighing alongside my Question, so that whoever answers is choosing between the same alternatives I was.
38. As the agent, I want my Question answered without my having to wait for a human, so that an unattended Run continues rather than stalling.
39. As the agent, I want the Protocol present in every fresh context, so that clearing or compaction does not leave me unable to participate.
40. As the agent, I want a clean context for work that does not need the previous phase's conversation, so that I am not carrying irrelevant history into a long run.
41. As the agent, I want the previous phases' Artifacts on disk, so that a cleared context costs me nothing I actually needed.
42. As a workflow author, I want to write only States and Prompts, so that I do not carry Naiad's Protocol boilerplate in every Prompt I write.
43. As a workflow author, I want a State to declare whether it Clears, so that I control which phases accumulate context and which start fresh.
44. As a workflow author, I want to mark a State as Terminal, so that Naiad can end a Run without knowing a special State name.
45. As a workflow author, I want to declare a State with no Prompt, so that I can place a human review point without needing a gate feature.
46. As a workflow author, I want an invalid Workflow file rejected at kickoff with a clear error, so that I find out before a Run starts rather than halfway through.
47. As a maintainer, I want every rule in one pure function, so that behavior is tested over plain data rather than against a fake environment.
48. As a maintainer, I want adapters to hold no rules, so that the parts I cannot easily test are also the parts with nothing to get wrong.
49. As a maintainer, I want everything about a Run reached through the Run, so that running two at once later is an addition rather than a rewrite.
50. As a maintainer, I want Naiad to depend only on documented Claude Code surfaces, so that a release does not silently break it.
51. As a maintainer, I want a log of every Announcement and every Action taken, so that I can reconstruct a Run that went wrong.

## Implementation Decisions

### Ownership and the Protocol

The agent is the only writer of a Run's State file; Naiad reads it and never writes it (ADR 0001). Progress is therefore always a record of the agent's judgment rather than a blackboard two parties race over.

The agent announces by running a command rather than editing the State file. Read-modify-write bookkeeping across a Cleared context is exactly the clerical work a model slips on, and a slip would be silently inert. The command owns ordering, writes atomically, and rejects an unknown State with an error naming the valid ones — an error the agent can see and correct.

Two agent-facing commands are needed: one announcing a State, one announcing a Question with its options. A third prints the Protocol for hook injection.

Announcements are ordered and distinct, so Naiad acts once per Announcement rather than once per change of value. A repeated State is a legitimate repeat — this is the entire implement loop, and Naiad models no iteration, no ticket list, and no exhaustion condition. Which tickets remain is recorded in the ticket files.

The Protocol is injected into every fresh context by a `SessionStart` hook on the `startup`, `clear`, and `compact` matchers — the three moments context is created or destroyed. It is Naiad's responsibility, never the Workflow author's, so that a Workflow file contains nothing but States and Prompts.

### Coupling to Claude Code

Naiad reads no Claude Code internals — not session transcripts, whose format is documented as internal and unstable, and not the terminal UI, whose scraping was v1's chief fragility (ADR 0002). Its entire coupling is three documented surfaces: sending keys to a tmux session, a `Stop` hook reporting that a turn ended, and a `SessionStart` hook injecting the Protocol.

Consequently a Question must carry its own text and options, because a question Naiad cannot see does not exist.

### Delivery

Naiad delivers when two independent facts hold: an Announcement is unhandled (intent), and a `Stop` has fired since it was made (safety). Neither substitutes for the other — `Stop` fires on every turn end including ones not ready to advance, and an Announcement alone races against an agent still working. Since Clearing is destructive, this race is not cosmetic.

Delivery is: optionally send `/clear`, then send the State's Prompt with the expected next State interpolated. The Workflow file owns the ordering, so the Prompt template names its successor by interpolation rather than by hand — one source of truth.

### Sessions

A Run is one tmux session from kickoff to Terminal State. Context hygiene comes from Clearing, not from spawning (ADR 0003). A State declares whether entering it Clears: the design phases accumulate context deliberately, each implement iteration starts fresh.

This is what preserves the human escape hatch — typing into the session only works if the session that did the work is still there. Sessions are spawned in bypass permissions mode so an unattended Run is never blocked by a permission prompt. The session is left alive when a Run ends.

### Gates and human intervention

A Gate State is a State with no Prompt. Naiad has nothing to deliver and takes no action; the human types into the session directly. This requires no gate feature — it falls out of the general delivery rule. Naiad exposes no approve or reject command; all human interaction is through the session.

Running with Gates skipped is a resolution-time filter over the Workflow's State list: Naiad interpolates a different next State. It never writes the State file, so the single-writer rule holds.

### Transitions

Any State declared in the Workflow is a legal target, including a backward one. Naiad validates only that the name exists. Enforcing forward-only order would deadlock the human's own intervention — being told to go back and fix the spec, the agent would be unable to comply, and the human has no override because only the agent announces.

An Announcement naming something other than the expected next State is a Deviation: permitted and delivered, but recorded and surfaced in the Run summary, because it is more often a confused agent than a decision.

### The Answerer

A Question is resolved by a separate headless Claude session, one per Run, resumed across every Question so that later answers cannot contradict earlier ones — the human reads them together as one log.

Its authority boundary is whether the answer is discoverable in the repository. Architecture, conventions, naming, module ownership: inferable, and its to settle. Credentials, external spend, business priorities: not in the repo, so answering would be invention dressed as inference. It escalates those.

Resolving a Question is two steps rather than one, because the Answerer returns either an answer or an escalation and choosing between them is a rule. The decision function asks for the Answerer to be consulted; its outcome comes back as a signal; the next decision either sends the answer into the session or notifies an escalation. Handling that branch where the Answerer is called would put a rule in the adapter layer.

Escalation is mechanically identical to a Gate State — Naiad stops acting and notifies. This is deliberate: Gate reached, Answerer escalated, agent fell silent, and agent hung all resolve to notify-and-wait. Naiad needs one behavior here, not v1's taxonomy of six.

Notification is once per Announcement, not once per tick. Every one of those conditions persists across ticks with identical signals, so without this the operator receives a notification every couple of seconds until they wake up. Whether a notification has already been sent for the current Announcement is therefore a signal the decision function reads, reset when a new Announcement arrives.

A Run that needs a human stays alive and keeps ticking — the human types, the agent announces, and delivery resumes. Only a Terminal State ends a Run and stops the tick loop. These are genuinely different outcomes, and collapsing them would force the tick loop to decide out-of-band whether to keep running, putting a rule outside the pure core.

The Answer log is written by Naiad rather than the agent, since Naiad holds both the Question and the Answer. The agent cannot fail to log an answer it never saw.

### Recovery

An agent that goes idle without announcing has usually forgotten the Protocol. Naiad sends at most **two** Nudges — a reminder of the Protocol — and then notifies and waits. The bound is the point: unbounded nudging is Naiad fighting the agent, and an agent that is genuinely stuck will never recover from being asked again. Two is chosen because a single reminder covers the common case of a forgotten Announcement, a second covers a reminder that arrived while the agent was mid-thought, and a third has never been the difference between a Run that recovers and one that does not. Each Nudge knows which attempt it is, so the second can be worded more firmly than the first.

A session that hangs never fires `Stop` at all, so a wall-clock timeout with no `Stop` and no Announcement resolves to the same notify-and-stop.

### Storage

A Run's files live in a Naiad-owned directory outside the target repository: the State file, the Answer log, the log, and the metadata linking the Run to its tmux session and Answerer session. The target repository is never written to by Naiad.

This protects the State file from an agent running `git add -A` during an implement loop, or from an agent "tidying up" a mysterious file in its diff. It also means a Run's record outlives the working copy, which matters once Runs execute in disposable worktrees.

### Structure

Written in Python. Packages by dependency rather than by feature:

- **domain** — pure. Workflow parsing and validation, the decision function, Protocol text. Imports nothing from the other packages; if a rule needs I/O, the I/O moves to the caller.
- **runtime** — per-Run state. The Run itself, atomic State file access, the Answer log.
- **adapters** — everything touching the outside world: tmux, headless Claude, notification.
- **cli** — the human-facing entry point and the agent-facing commands.
- **hooks** — installation and the hook scripts.
- A wiring layer gathering signals, calling the decision function, and carrying out the result.

Every rule lives in one pure function (ADR 0004):

```
decide(workflow, signals) -> Action

signals:
  announcement      seq, state, question | None      the agent's latest
  handled_seq       last seq Naiad acted on
  stopped           has a turn ended since the announcement?
  consultation      none | answered(text) | escalated(reason)
  notified          already notified for this announcement?
  nudges            nudges sent for this announcement
  idle_for          elapsed since the last signal of any kind

Action:
  Deliver(prompt, clear, deviated)  state announced, turn ended — send it
  Consult(question)                 hand the Question to the Answerer
  Respond(answer)                   append to Answer log, send into session
  Nudge(attempt)                    idle, nothing announced, under the bound
  Notify(reason)                    human needed — Run stays alive, keep ticking
  Finish(outcome)                   Terminal State — Run over, stop ticking
  Nothing                           working, waiting on a human, already notified
```

Three distinctions in that set are load-bearing and were arrived at by walking every rule through it:

`Consult` and `Respond` are separate because consulting the Answerer and acting on what it says are separated by a rule — the outcome may be an answer or an escalation. `Respond` also appends to the Answer log, an effect `Deliver` does not have, so the two cannot be collapsed without a conditional in the tick loop.

`Notify` and `Finish` are separate because only one of them ends the Run.

`Nothing` covers "already notified", which is what stops a Gate State from notifying on every tick.

`deviated` is a field rather than an Action because delivery happens regardless; it exists so the log and Run summary can record that the Run left the expected path.

Nothing about a Run may be module-global — not its paths, session, Answerer, nor last handled Announcement. Only one Run executes today, so this discipline buys nothing immediately; it is what makes concurrent Runs an addition later, and it is not recoverable after the fact.

Run resolution must not depend solely on an environment variable. Naiad sets one when it spawns a session, but a variable cannot be injected into a running process, so resolution sits behind a single seam that can also identify a Run by tmux pane or by the recorded Claude session id. Hooks are installed independently of a Run and do nothing when none is attached. Both keep session adoption possible later at no cost now.

## Testing Decisions

Work test-first throughout: Red — write a failing test for the intended behavior and confirm it fails for the expected reason; Green — write the minimal code to pass; Refactor — improve with tests green, naming the refactor candidates considered and recording a verdict even when the verdict is to keep as-is. Where a unit test is not possible, the Refactor check still happens and verification is by manual smoke.

A good test here asserts external behavior only. For the decision function that means: given these signals, this Action — never how the decision was reached. For the agent-facing commands it means the contract the agent actually meets: exit status, the resulting State file, and the error text. A test that would break on an internal rename is testing the wrong thing.

There is no prior art; this is a greenfield repository. The convention established here is the prior art for what follows.

**Seam 1 — the decision function.** The primary seam. Table-driven tests over plain data covering every rule: deliver on an unhandled Announcement; wait when the turn has not ended; notify once at a Gate State and do nothing on every tick thereafter; consult the Answerer on a Question; send an answer and log it; notify an escalation; nudge twice and no more, then notify; notify on hang; flag a Deviation while still delivering; finish on a Terminal State and only then stop; resolve the next State with and without Gates. No tmux, no subprocess, no clock, no sleeping, no fakes.

Two of these deserve explicit tests because they are the failures a reasonable implementation makes: that a persisting condition notifies exactly once rather than every tick, and that `Notify` leaves the Run tickable while `Finish` does not.

**Seam 2 — the agent-facing commands, invoked as real subprocesses** against a temporary Naiad directory. This is the contract the agent depends on and its failures are the silent ones: sequence allocation across successive Announcements, atomic writes, rejection of an unknown State with the valid names listed, and recording a Question with its options. Testing at the process boundary exercises it as the agent will meet it, without dragging in tmux or Claude.

**Also tested:** Workflow parsing and validation — a well-formed file produces the expected States, and a malformed one is rejected at kickoff with an error naming the problem.

**Manual smoke only:** the tmux, Claude and notification adapters, the hook scripts, and the wiring layer. These are to hold no logic worth testing; if one begins to, that logic belongs in the pure core. Verification is running a real Workflow end to end.

A fake-tmux integration seam was considered and rejected: the fakes would have to stay honest to be worth anything, and green tests over a system that does not actually work is the specific failure v1's test suite exhibited.

## Out of Scope

- **Queueing and scheduling.** One Run at a time, started by hand. No cron, no triggers, no routines, no queue, no confirm mode. The single-Run engine must be built so that these are additive.
- **Concurrent Runs.** One at a time. The discipline that keeps this possible — nothing module-global, everything reached through the Run — is in scope; the feature is not.
- **Branching Workflows and the classifying State.** Decided (ADR 0005) but deferred, with the bug branch's shape still open. The Workflow format must tolerate a State declaring multiple successors even while nothing uses it.
- **Starting a Run from inside an existing session.** Deferred. The two constraints that keep it possible — run resolution not keyed solely to an environment variable, hooks installed independently of a Run — are in scope.
- **Defending against Protocol leakage.** The fallback is known and additive; the leak rate is unmeasurable before real Runs. Instrumentation is in scope: log every Run that ends in notify-after-Nudge together with what the agent was doing.
- **Enforcing Artifact discipline.** Nothing verifies that a Cleared State's predecessor wrote what it needs. Safe for the shipped Workflow by construction.
- **A supervisor judging Artifacts.** The agent judges its own readiness; that is the point.
- **Model selection, availability probing, and fallback chains.** v1 machinery with no equivalent here.
- **Any workflow other than the Matt Pocock feature chain.** Naiad is workflow-agnostic by construction, but only one Workflow file ships.

## Further Notes

The shipped Workflow is the Matt Pocock feature chain: grilling, a human Gate for review, spec, tickets, the implement loop, PR, review fix. The implement loop is a single State announced repeatedly, Clearing between iterations.

Two risks are recorded as deferred issues and worth reading before implementation. Protocol leakage is the larger: skills such as grilling ask interactively by design, and the Protocol is one instruction arguing with another. When it leaks the failure is quiet — the agent blocks on a dialog nobody will answer and the Run dies having done nothing since. The known fallback intercepts the tool rather than instructing against it, but it relies on an undocumented channel and catches only tool-call questions.

The second risk is that Clearing is only safe because Artifacts carry the meaning between States, and nothing checks this. The shipped Workflow satisfies it by construction. The bug branch already does not, which is why the deferred branching issue must produce a diagnosis Artifact it would not otherwise write.

Two deferred decisions constrain work happening now, and both are cheap now and awkward to retrofit: run resolution behind a single seam rather than keyed to an environment variable, and hooks installed independently of any Run.

Naiad v1 lives at `/Users/janlibs/dev/claude-instantiator` and is worth consulting for plumbing — driving tmux, hook wiring, headless call handling — while treating its architecture as the thing being replaced.
