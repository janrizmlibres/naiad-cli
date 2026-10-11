# An Entry may name a setting for a State

ADR 0026 put a phase's Model and Effort in the Workflow file, because which model a phase needs is usually a judgment about the phase's nature, and it kept them out of the Entry on purpose: "a real 'this whole task needs the big model' case can earn one later". The case that earned it runs the other way. A queue of small, well-specified tickets does not need the model the Workflow gives `implement`, and the operator queueing them is the one party who knows that. Editing the Workflow file for one queue changes every other Run that reads it, and the Workflow library shares one file between them all.

We decided an Entry may carry settings, each naming the State it is for: `--model implement=sonnet --effort implement=medium`, repeatable, on every entrance that describes work — `naiad adopt`, `naiad queue add` and `naiad run`. For the State it names, an Entry's setting beats the State's own key, which beats the file-level default, which beats no opinion (ADR 0040). It is a declaration like the others and nothing more: it reaches the Session as a Switch, is compared against the Belief, is re-typed after a Notify, and at kickoff rides the launch flags when it names the first State. A State it gives an opinion to that the file left keyless is ordinary, and a keyless State after it inherits by stickiness exactly as ADR 0040 already allows.

A setting is checked where the start State is, when the Entry is queued and again when the Supervisor starts it. Refused are a bare value naming no State, a State the Workflow lacks, a Gate State or Terminal State — neither is ever typed a Switch, so the setting would do nothing while looking as if it did — and one State named twice for the same setting, since a flag an agent wrote should never lose to another quietly. A State the Run may never reach is kept, because where a Run goes is known only as it goes. A Workflow edited under a live Run, so that a named State stops delivering, leaves the setting unused rather than parking the Run: a wrong price is not worth a stalled night.

## Considered options

**One setting for the whole Run** — `--model sonnet`, applied to every State that delivers a Prompt — was the smaller surface and the one this ADR's case asked for first. It was rejected for what it reaches without being named: a Run adopted at `tickets` walks through `pull-request`, and one entering at `classify` may walk through `grill`, the phase ADR 0026 held up as the one that earns the expensive model. Naming the States keeps the operator's opinion exactly as wide as they stated it. The adopt skill carries the convenience instead: told a model with no States, it asks, offering every prompted State reachable from the start State as the suggested answer.

**Batch file keys** were left out for now. A Batch file refuses keys it does not read, so a `model` written there fails loudly rather than being ignored, and adding it later is an extension, not a migration.

**The Answerer** stays the Workflow's alone. Reserving a State name such as `answerer` to reach it would collide with a State of that name and give one flag two meanings.

## Consequences

ADR 0026's claim that a State's settings are legible in the Workflow file now holds for the Workflow's defaults only; a Run's actual settings are the file's overlaid with its Entry's, and the queue listing shows the Entry's so an operator can read them before a night's work. The Run log's `switched` lines remain the record of what was typed, without saying where the value came from.

The Entry and the Run gain a field on disk, read with a default so that records written before it still load.
