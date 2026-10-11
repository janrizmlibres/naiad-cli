# 07 — A Gate tells both sides what follows

Status: resolved
Mode: AFK
Blocked by: 01
Spec: [PRD](../PRD.md), "The engine"; map ticket [14](../issues/14-what-the-agent-and-the-human-each-know-at-a-gate.md)

**What to build:** Two changes at a Gate, with nothing typed into the Session.

- **The notification names what follows.** It reads `state 'review' is a Gate State and is waiting for you; next: implement`. At a branching Gate the candidates are joined as the Protocol joins them. When nothing follows, no clause is added.
- **The announce reply tells the agent.** When Naiad will park on the Gate the agent just announced, `naiad announce` replies: "`<gate>` is a Gate: a human takes it from here. End your turn and wait for them." It follows that, word for word, with the Protocol's expectation sentence for the Gate: the single successor, "whichever applies" at a fork, or the nothing-expected sentence. Whether Naiad will park is decided by the same predicate that makes the decision function notify for a Gate. So a Gate that a `--skip-gates` Run resolves past, and every other State including a Terminal one, keeps the plain `announced X (n)` reply.

- [ ] The Gate notification carries `next: <state>`, the joined candidates at a fork, or no clause.
- [ ] Announcing a Gate in a supervised Run returns the Gate reply plus the expectation sentence.
- [ ] Announcing the same Gate in a `--skip-gates` Run returns the plain reply.
- [ ] Ordinary and Terminal Announcements are unchanged.
- [ ] Built test-first, Refactor verdict recorded.
