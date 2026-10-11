# What the agent and the human each know at a Gate

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

At a Gate the agent's last Protocol line says "announce `<the Gate>`", because the expectation line is injected only into fresh contexts and a Gate creates none. So the agent standing at `review` has never been told that `implement` comes next, and the human clearing the Gate has to know the Workflow well enough to say it. The Gate notification names the Gate and nothing after it. In the starter's prototype Run the operator had to type "announce implement". Decide: whether the Gate notification names the State that follows (the declared order's next, or the candidates where the Gate branches) so the human can say it; whether Naiad types the expectation line into the Session on a Gate, which is a delivery into a context the human may be typing in and contradicts "Naiad delivers nothing at a Gate"; whether the `naiad state` rejection's list of valid names is enough; and what the first-run documentation tells the human to type at a Gate. Surfaced by the starter workflow ticket.

## Answer

Both sides are told what follows the Gate, and Naiad still delivers nothing into the Session. The human's hand-off becomes a verdict instead of a State's name.

- **The notification names what follows.** `state 'review' is a Gate State and is waiting for you; next: implement`. If the Gate branches, the candidates are joined as the Protocol joins them (`next: bug or feature`). If nothing follows, no clause is added. The names come from `next_states` for the Gate; nothing new is computed. The notification carries no hint of what to type.
- **The agent learns it from the announce verb's reply, not from a delivery.** When `naiad announce <gate>` succeeds and Naiad will park on that Gate, the verb's stdout says: "`<gate>` is a Gate: a human takes it from here. End your turn and wait for them." It follows that with the Protocol's own expectation sentence, word for word: the single successor, "whichever applies" at a fork, or the nothing-expected sentence. The reply is a tool result the agent reads, so "Naiad delivers nothing at a Gate" stays true. Nothing clears the context before the human arrives, so the line is still there when they do. Typing the expectation line into the pane was rejected: it is a delivery at a Gate, it can land on top of the human's typing, and the Belief and Submission rules would have to account for it.
- **The reply is a Gate reply only where Naiad parks.** It is decided by the same predicate that makes `decide` notify for a Gate. So a routine Gate that a `--skip-gates` Run resolves past, if announced anyway, gets the plain reply.
- **Every other Announcement keeps `announced X (n)`**, and so does a Terminal State. At an ordinary State the agent must end its turn and wait for Naiad's Prompt; a reply naming the next phase would invite it to start that phase early, and a Clear would wipe the line anyway. What the Session is told when a Run ends is outside this ticket.
- **The rejection's list of valid names is unchanged.** It is a safety net for typos, not the route: it lists every State without saying which one is expected.
- **Documentation.** The README's first-run walkthrough, at `review`: the notification says `review` is waiting and `implement` is next; read `PLAN.md`, then type a verdict into the session **and send it** ("go ahead", or what to change). The agent announces the next State itself; name a State only to send it elsewhere. `docs/workflow-authoring.md` says the same where it explains Gates: a Gate's hand-off is a verdict.
- **Glossary.** **Gate State** gains one sentence: the agent learns what follows from its own Announcement's reply, the human from the notification, so the hand-off is a verdict. No ADR: the change is cheap to reverse and was not a hard trade-off.
