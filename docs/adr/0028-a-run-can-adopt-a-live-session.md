# A Run can adopt a live session

The operator's real flow does not always start with Naiad. They open a Claude Code session themselves, run the grilling interview by hand, and only then want the machine to take over — spec, tickets, the implement loop, the tail — without losing the conversation the interview built, which is exactly what the non-Clearing States feed on. Kickoff cannot serve this: it spawns a fresh session, and a fresh session has none of that context. The resolution seam anticipated the need — "adopting a running session later must remain possible" (`naiad/runtime/resolve.py`) — and this decision cashes it in.

The shape is an **Adoption**: a new agent-facing subcommand, `naiad adopt`, run from inside the live session on the human's stated intent ("start to-spec"). It writes an Entry marked to attach rather than spawn, and returns at once — an agent's tool call must not block. The Supervisor remains the one entrance to starting Runs (ADR 0014): it takes the Entry in Lane order, attaches the Run to the existing pane instead of opening a session, and delivers the start State's Prompt only after the current Turn has ended, the same rule an Answer already obeys. An Adoption *waits* its Lane turn like any Entry; it is not a jump of the queue. A flag on `naiad queue add` was rejected because "add to the backlog" and "take over this session" are different intents, and a Naiad-side watcher was rejected outright — it would read Claude Code internals (ADR 0002).

Five subsidiary choices, each a real fork:

- **tmux only, for now.** Delivery is typing into a pane; a session outside tmux has nothing Naiad can type into. The operator already works in tmux, so the rule costs nothing today. A second delivery mechanism is acknowledged as a possible future, not built.
- **The Protocol arrives as the command's output.** The manual session never saw the SessionStart injection and no Clear will fire before the agent must announce. `naiad adopt` prints the Protocol (the existing `naiad protocol` text) plus one closing line — end your turn; the Prompt comes when the Lane is free. Typing it into the pane instead would be a second delivery with new ordering rules.
- **The adopt contract carries the branch.** Both Workflow branch heads are skipped, so the ADR 0022 discipline moves into the act of adopting: the agent passes a branch the human already made, or derives, creates, and declares one in the same turn. The existing claim check refuses collisions. Making the start State a third branch head was rejected — it would pollute the ordinary path where the head already prepared the branch.
- **The agent writes the Task.** The operator's words are a whole conversation, not a line; the agent distils them into the `--task` the Entry requires, because it is the one party holding that conversation. The Subject stand-in (ADR 0024) was rejected — an Adoption has no natural Subject either.
- **No Supervisor running: warn, never spawn.** The output says the Entry is queued and quotes `naiad queue watch`; the agent relays it. A Supervisor launched as a side effect of a tool call has no terminal, no owner, and no end.

Unlike kickoff, which ignores the first State's Clear flag because a new session has nothing to discard, an Adoption **honors** it: the session is full of context, and the Workflow's declaration of a clean start is not Naiad's to overrule. Adopting at a non-Clearing State is the whole point of the feature; adopting at a Clearing one is the operator saying the conversation is not needed.

The contract is taught where the hooks are installed: `naiad install` also writes a user skill (e.g. `~/.claude/skills/naiad-adopt/`) whose description triggers on the operator's intent phrases and whose body holds the whole adopt discipline. The contract is Naiad's, so the file that teaches it is versioned and reinstalled with Naiad rather than hand-maintained and left to drift.

## Consequences

Attachment becomes a second way a Run meets its session, so everything that assumed "the Run spawned it" — session naming, the environment-variable shortcut, model and effort switches on first delivery — must go through the resolution seam instead. The one-entrance rule survives intact: adopt enqueues, only the Supervisor starts.

The adopted agent operated un-Protocolled until the moment of adoption; everything it does between reading the adopt output and its turn ending is on trust, as every Protocol act already is.
