# Terminal States, Deviations, and the Run log

Status: ready-for-agent
Blocked by: 02-the-core-loop
Spec: `.scratch/core-engine/PRD.md`

## What to build

How a Run ends, and what it leaves behind.

**Ending.** A Workflow marks its last State as Terminal; announcing it finishes the Run, notifies the operator that the work is done, and stops the tick loop. This is deliberately distinct from notify-and-wait: a Run that needs a human stays alive so that typing revives it, whereas a finished Run is over and should not leave something ticking. Collapsing the two would force the tick loop to decide out-of-band whether to keep running, which is a rule outside the pure core. Terminal is declared by the Workflow rather than by a State name Naiad recognises, so Naiad stays ignorant of any particular Workflow's meaning.

The session is left alive after a Run ends. Killing it destroys the evidence the operator would want when something looks wrong.

**Deviations.** Any State declared in the Workflow is a legal target, including a backward one — the human may have redirected the agent mid-phase, and enforcing forward-only order would deadlock exactly that intervention, since the agent could not comply and the operator has no override. But an Announcement naming something other than the expected next State is recorded, because it is more often a confused agent than a decision. It is delivered regardless; the record exists so the operator can see that the Run left the expected path.

**The Run log.** Every Announcement received and every Action taken, in order, in enough detail to reconstruct a Run that went wrong — which State, which Action, why. This is the diagnostic that turns "it produced something strange overnight" into a readable sequence, and it is what makes the deferred Protocol-leakage instrumentation possible later.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] Announcing a State marked Terminal ends the Run and notifies the operator that it completed
- [ ] The tick loop stops after a Run ends and does not act on anything further
- [ ] Notifying that a human is needed does not end the Run, and the tick loop continues — asserted alongside the Terminal case so the two cannot be conflated
- [ ] The session is still alive after a Run ends
- [ ] Terminal is read from the Workflow; no State name is special-cased
- [ ] An Announcement naming a State other than the expected next one is still delivered
- [ ] Such an Announcement is recorded as a Deviation, naming both the expected State and the announced one
- [ ] An Announcement naming the expected next State is not recorded as a Deviation
- [ ] Every Announcement and every Action is written to the Run log in order
- [ ] The Run log distinguishes delivering a State's Prompt from sending an answer to a Question
- [ ] A completed Run's log is sufficient to reconstruct which States it passed through and why each Action was taken
