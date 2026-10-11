# The agent owns workflow state

Naiad v1 tracked where each piece of work had got to and decided when it could move on, which meant every edge case in every workflow had to be modelled inside Naiad. We have inverted this: the agent announces its own State, and Naiad only reacts. The agent is the only writer of a Run's State file — Naiad reads it and never writes it — so progress is always a record of the agent's judgment rather than a blackboard two parties race over.

This is what makes Naiad workflow-agnostic. Deciding whether the spec is good enough to start writing tickets is a judgment about the work, and the agent is holding the work; Naiad is not. It also means an agent can decline to advance when something needs attention, and Naiad needs no vocabulary for that case at all.

## Consequences

Announcements are ordered and distinct, so Naiad acts once per Announcement rather than once per change of value. A repeated State is therefore a legitimate repeat — this is the whole of the implement loop, and Naiad models no iteration, no ticket list and no exhaustion condition. Which tickets remain is recorded where it belongs, in the ticket files.

The agent announces by running a command rather than by editing the State file directly. Read-modify-write bookkeeping across a cleared context is exactly the sort of clerical task a model slips on, and a slip would be silently inert; a command owns the ordering, writes atomically, and rejects an unknown State with an error the agent can see and correct.
