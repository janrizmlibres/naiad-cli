# One session per Run, cleared between States

> Excepted by ADR 0062.

A Run is a single Claude Code session from kickoff to completion. Where a State needs a clean context it is Cleared rather than replaced, and whether to Clear is declared per State: the design phases accumulate context deliberately, while each iteration of the implement loop starts fresh.

The alternative — a new session per State — was rejected because it buys nothing that Clearing does not, while costing session lifecycle management, and because it would break the human's escape hatch. When a Run parks at a Gate State the human types into the session directly, and that only works if the session that did the work is still there to be talked to.

## Consequences

Clearing is safe only because Artifacts carry the meaning between States. This is a real constraint on Workflow authors rather than an observation: a State that communicates through conversation alone cannot be Cleared, and a Workflow that relies on it will fail in a way that looks like the agent forgetting.
