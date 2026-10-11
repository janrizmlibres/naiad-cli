# The Queue records no status of its own

> Amended by ADR 0022, ADR 0042.

The Supervisor has to know whether an Entry is waiting, running, parked or done. The obvious way is a status field on the Entry that the Supervisor updates as it goes.

We decided against, and an Entry records only which Run it became. Everything else is asked of that Run: an Entry with no Run is waiting; one whose Run has finished is done; one whose Run has been notified for its current Announcement is parked; anything else is running.

Every one of those facts already exists inside the Run, written by the party that observed it. The Run log is what a watch consults before its first tick to refuse to drive a Run that is over, and the notice record is what stops a persisting condition notifying on every tick. Copying them onto the Entry does not create knowledge, it creates a second copy that can disagree with the first — and a status the Supervisor writes about work it is not doing is the blackboard two parties race over that the State file was deliberately not allowed to be. The same objection applies for the same reason, one level up.

The failure it avoids is concrete rather than theoretical. Kill the Supervisor mid-Run and a status field is left saying `running` about nothing, and a field that lies has to be reconciled by something, on a schedule, against the truth it was copied from. Deriving cannot lie, because it never claimed anything the Run had not.

Crash recovery then needs no design at all. Restarting the Supervisor finds the first Entry whose Run has not finished and watches it again, and watching already handles both outcomes correctly: it reports that a finished Run has finished and returns, and it picks an unfinished one back up mid-flight. There is no resume path, because there is no state to resume.

## Consequences

Reading the Queue means reading a Run directory per Entry rather than one file. At the scale of a personal backlog this is nothing; if it ever stops being nothing, the answer is a cache with the Runs still authoritative, not a status field with the Runs still authoritative.

An Entry is therefore almost empty: what a Run would have been told at kickoff, plus the Run it became. Everything else about it is a question, and every question has exactly one place that answers it.

The Predecessor rule inherits this. It walks Entries and reads their Working branches, which are facts recorded when the Entry was made, and never asks what became of the Run — because what became of it is a question about git, and the answer belongs to the agent rather than to the Queue.
