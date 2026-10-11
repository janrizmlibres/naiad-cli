# The Matt Pocock Workflow and end-to-end verification

Status: ready-for-human
Blocked by: 03-protocol-injection-and-next-state-resolution, 04-notify-and-wait, 05-questions-and-the-answerer, 06-terminal-states-deviations-and-the-run-log
Spec: `.scratch/core-engine/PRD.md`

## What to build

The Workflow that ships, and proof the whole thing works against a live repository.

The Workflow is the Matt Pocock feature chain: a grilling interview, a human Gate for reviewing it, a spec, tickets, an implement loop, a pull request, and a review fix, ending at a Terminal State. Each State invokes the corresponding user skill verbatim as its Prompt, so that no logic is duplicated out of a skill and into a Workflow file. The Gate has no Prompt. The implement loop is a single State declaring Clear, announced once per ticket. Only the phases that genuinely need the previous conversation accumulate context; the rest Clear.

This is also where the parts held back from automated testing get verified, because they hold no logic worth testing and the only honest check is running them for real: driving a session, consulting the Answerer, notifying, and the hook scripts. Running the chain end to end against a real repository is the verification.

Two things must be observed rather than assumed during that run:

**Protocol leakage.** Skills such as grilling ask interactively by design, and the Protocol is one instruction arguing with another. When it leaks the agent blocks on a dialog nobody will answer, and the Run dies quietly having done nothing since. The Run log must make this countable — every Run ending in a notification after Nudges, recorded with what the agent was doing — so that the deferred decision about intercepting the tool is made against a number rather than an impression. See `.scratch/deferred/issues/01-protocol-leakage.md`.

**Artifact discipline.** Clearing is only safe because Artifacts carry meaning between States, and nothing enforces it. The chain satisfies this by construction, but a State that appears to have forgotten what it just did is the symptom to watch for, and it will look like a model failure rather than a Workflow bug. See `.scratch/deferred/issues/02-clear-and-artifact-discipline.md`.

## Acceptance criteria

- [x] The Workflow file declares the full chain in order, with the review Gate having no Prompt and the last State marked Terminal
- [x] Each State's Prompt invokes the corresponding user skill verbatim, with the next State interpolated
- [x] The implement loop State declares Clear; the design phases that need prior context do not
- [x] The Workflow parses and validates, and a Run can be started from it
- [ ] Manual smoke: a full unattended Run against a real repository reaches its Terminal State
- [ ] Manual smoke: the run parks at the review Gate, notifies once, and resumes after the operator types into the session
- [ ] Manual smoke: at least one Question is raised, answered by the Answerer, and appears in the Answer log with its options and the answer chosen
- [ ] Manual smoke: the implement loop delivers once per ticket with a cleared context each time
- [ ] Manual smoke: a Clear and a compaction each leave the agent still able to announce
- [ ] The Run log of that run is sufficient to reconstruct what happened without consulting the session
- [ ] Any Protocol leak observed is recorded on the deferred Protocol-leakage issue with what the agent was doing at the time
- [x] Refactor check performed across the work as a whole, with candidates named and a verdict recorded even where the verdict is to keep as-is

The unticked criteria are the manual smoke, which is the operator's to run: the
procedure is `docs/smoke/matt-pocock.md`, and its Results section is where they
are recorded. It takes two Runs — a supervised one for the Gate State, one with
`--skip-gates` for the unattended path — because those two criteria cannot both
hold in a single Run.
