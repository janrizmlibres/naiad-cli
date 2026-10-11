# A completed Child's Session is closed

> An exception to ADR 0003's Session left alive, and to ADR 0035's release.

A Session outlives its Run on purpose. It holds the evidence of what the Run did, and it is the escape hatch: a person can type into it after the work has stopped. Children change the arithmetic (ADR 0060). A feature of thirty tickets leaves thirty idle Claude Code sessions, at roughly 0.8 GB each with their MCP servers, and every one of them counts against the memory that Capacity's pressure check reads (ADR 0061). Within a single night they would hold back the very Runs they were spawned beside.

We decided Naiad closes a Child's Session once the Child **completed** and its Parent has been told of it at a Join State. This is the first time Naiad ends a Session rather than leaving it. The transcript stays on disk, and so do the Run log and the Answer log, so the evidence survives. Only the live process goes, and the escape hatch it offered has no use left: the Child's work has been taken into its Parent.

A Child that was **cancelled** keeps its Session, and so does one that has not been taken in. A Cancellation is a person stepping in, and a person who stepped in may want to type into what they stopped. A parked Child is not finished, so it is not a candidate.

## Considered options

**Keeping every Session, as before.** Rejected for the memory reason above. Closing the Sessions by hand would be the morning chore this project exists to remove.

**Closing a Child's Session as soon as it reaches its Terminal State.** Rejected, because the Parent has not yet taken the work in. Until it has, the Child's Session is the nearest place to look if the merge goes wrong.

## Consequences

"A Session outlives its Run" now has one exception, stated in the glossary beside the rule. A top-level Run's Session is still kept, released and never closed.
