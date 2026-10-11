# A pure decision core

Every rule Naiad has — when to deliver, when to Answer, when to Nudge, when to notify, when a Run has ended — lives in one pure function over plain data. The adapters that drive a terminal session, call a headless Claude, and post notifications hold no rules of their own; they gather signals, hand them over, and carry out whatever comes back.

Naiad v1 had no such seam: every module reached for a subprocess or the filesystem, so nothing could be tested without standing up a fake environment, and the test suite grew to nearly twice the size of the code it covered. Grouping that code into directories would not have helped, because the entanglement was in the dependencies rather than the layout.

## Consequences

Nothing about a Run may be module-global — not its paths, its session, its Answerer, nor its last handled Announcement. Every one is reached through the Run it belongs to. Only one Run executes today, so this discipline buys nothing immediately and will feel like ceremony; it is what makes concurrent Runs an addition later rather than a rewrite, and it is not recoverable after the fact.
