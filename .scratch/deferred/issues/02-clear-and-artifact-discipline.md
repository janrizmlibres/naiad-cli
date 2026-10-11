# Clearing depends on Artifact discipline, and nothing enforces it

Status: needs-info
Trigger: authoring a second Workflow, or any Run where a Cleared State behaves as though it lost context

## The risk

Clearing a State's context is safe only because Artifacts carry the meaning between States (ADR 0003). The Matt Pocock chain satisfies this by construction — `CONTEXT.md`, the ADRs, the PRD and the issue files hold everything a later phase needs, so a Cleared session rebuilds its understanding by reading them.

Nothing checks this. A Workflow author can mark a State `clear = true` when the State it follows communicated only through conversation, and Naiad will faithfully discard exactly the context that mattered. The symptom is an agent that appears to have forgotten what it just did — which reads as a model failure rather than a Workflow bug, so it will be misdiagnosed.

The risk is near zero for the shipped Workflow and rises the moment a second one is written, especially by someone who did not sit through this design.

## Why it is deferred

There is one Workflow and it is known to be safe. Any enforcement built now would be guessing at what a violation looks like.

## Options when it becomes real

- Document the constraint where a Workflow author will meet it, as a rule about what a Cleared State may assume.
- Have a State declare the Artifacts it depends on, and refuse to Clear when they do not exist. This is a real check but starts teaching Naiad about Workflow semantics — weigh it against ADR 0001 before adopting it.
- Leave it undefended and rely on the symptom being recognisable, provided the failure mode is written down somewhere the next author will look.
