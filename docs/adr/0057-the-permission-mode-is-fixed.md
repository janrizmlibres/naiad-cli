# The permission mode is fixed

Every Session Naiad spawns, and every Answerer consultation, runs in `bypassPermissions` mode, and no Workflow key, environment variable or flag changes that. It looks like the obvious safety setting to add. We decided not to add it, because a Session that stops at a permission prompt has nobody to answer it. Naiad would read the dialog as silence and then as idleness, type a Nudge into it, and park the Run with no reason anyone could see. A settable mode would only be honest if the engine could recognise a permission prompt, and that is a new signal for the engine to read, not a setting.

An adopter who wants containment gets it from the machine, not from Naiad: a container, a VM or a devcontainer that holds only what a Run may touch. The README warns about the mode and says this.

## Considered alternatives

**A Workflow key `permission_mode`.** Rejected: any mode other than bypass lets a Run stall on a prompt the engine can't see.

**An allowlist of tools per Workflow or State.** Rejected for the same reason. A tool the list forgot shows up as the same unexplained stall.
