# Starting a Run from inside an existing session

Status: needs-info
Trigger: wanting to hand mid-conversation work to a Workflow rather than restarting it as a fresh Run

## What is wanted

Today a Run begins by Naiad spawning a session. The other direction should also work: the human is already talking to an agent, decides the thread deserves a full Workflow, and starts one from inside the TUI — `/grill-with-docs`, or a diagnosis chain — with Naiad adopting the session that already exists rather than creating one.

The appeal is that the conversation so far *is* the context. Restarting as a fresh Run throws away the exploration that led to wanting the Workflow in the first place.

## Why it is deferred

It inverts the ownership of the session, and every mechanism for attaching Naiad to a session currently assumes Naiad created it. None of that is hard, but it is a second lifecycle to design and test before the first one has been proven.

## Constraints this places on the work shipping now

These are cheap now and expensive to retrofit:

- **Run resolution must not depend solely on an environment variable.** Naiad plans to set `NAIAD_RUN_ID` when it spawns a session, but a variable cannot be injected into a process that is already running. Resolution must sit behind a single seam that can also identify a Run by tmux pane (`$TMUX_PANE`) or by the Claude session id the `SessionStart` hook already records, with the environment variable as a shortcut rather than the mechanism.
- **Hooks must be installed independently of a Run, and no-op when no Run is attached.** Hook configuration is read when a session starts, so a session that predates its Run will not pick up hooks installed at spawn time. Installing them once — for the project or the user — and having them do nothing unless a Run is attached makes adoption almost free, and costs nothing today.

## What the Queue work settled, and what it made harder

Grilling the Queue (ADRs 0012–0015) split this issue in two, and only half of it is still a feature.

**Enqueueing from a session needs nothing built.** A session can already run `naiad run` or `naiad queue add` through Bash, or write a batch file. A Run is then started later by the Supervisor in a session of its own. This covers the common want — "this thread deserves a full Workflow" — and it covers it better than expected, because the agent doing the enqueueing has the task and the repository's conventions in front of it and can fill in the Working branch that ADR 0015 requires. A paragraph of what the conversation established can cross as the Entry's task, which is the same Artifact-shaped handoff the design uses everywhere else.

**Adoption is what remains**, and two facts discovered since make it harder than this issue assumed:

- Runs are spawned in bypass permissions mode, which the "Permissions" question below anticipated. It is now load-bearing rather than probable: an unattended Queue running overnight cannot afford a Run that stalls on a permission dialog at 3am, and there is no human to clear it.
- Both heads of the shipped Workflow — `grill` and `diagnose` — declare `clear = true`. So adopting a session and entering the Workflow at either branch head destroys the conversation immediately. The "Prior context" question below is not an edge case; it is what the shipped Workflow does first, on every branch.

A third has been added by the Queue: everything in ADR 0015 assumes a Run starts by checking out its own Working branch from a resolved base. An adopted session is on whatever branch it is on, possibly with uncommitted work, and possibly on `develop`.

## Open questions

- **Permissions.** Runs are spawned in bypass permissions mode, which is what lets them proceed unattended. A pre-existing session is probably not in that mode and likely cannot be switched into it, so an adopted Run may stall on a permission prompt. This may be the hardest part, and may bound adoption to sessions that were already started permissively.
- **Prior context.** The adopted session carries a conversation. If the Workflow's first State declares `clear`, that conversation — the very thing that motivated adoption — is destroyed. Adoption probably needs to suppress the first clear, or the human needs to be asked.
- **Ownership at the end.** When the Run reaches its Terminal State, the session presumably returns to the human rather than being treated as a finished Run's artifact.
