# Questions and the Answerer

Status: ready-for-agent
Blocked by: 04-notify-and-wait
Spec: `.scratch/core-engine/PRD.md`

## What to build

The part that makes a Run genuinely unattended. Until now any question stops everything until a human answers. After this ticket the agent raises a Question and gets an answer back without a human being awake.

The agent announces a Question through a command, carrying its text and every option it was weighing. It supplies the options itself because Naiad reads no Claude Code internals (ADR 0002) — a Question Naiad cannot see does not exist — and because whoever answers, and whoever later reviews that answer, should be choosing between the same alternatives the agent faced.

Resolving a Question is two steps rather than one, because the Answerer returns either an answer or an escalation and choosing between those is a rule. The decision function asks for the Answerer to be consulted; the outcome comes back as a signal; the next decision either sends the answer into the session or notifies an escalation. Handling that branch at the point the Answerer is called would put a rule in the adapter layer, against ADR 0004.

The Answerer is a separate headless Claude session, one per Run, resumed across every Question so that later answers cannot contradict earlier ones — the operator reads them together as a single log, and an Answerer that re-derives the architecture each time will disagree with itself.

Its authority is bounded by whether the answer is discoverable in the repository. Architecture, conventions, naming, which module owns a concern: inferable, and its to settle. Credentials, external spend, business priorities: not in the repository, so answering would be invention dressed as inference. It escalates those, and escalation is mechanically the notify-and-wait already built.

The Answer log records every Question with its options and the answer chosen. Naiad writes it rather than the agent, because Naiad holds both halves — the agent cannot fail to log an answer it never saw. This is what the operator reads at a Gate to judge whether an unattended Run went astray.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] Announcing a Question records its text and every option, and orders alongside State Announcements
- [ ] A Question with no options is rejected with an error explaining why options are required
- [ ] The agent-facing command is exercised as a real subprocess, asserting exit status, resulting file, and error text
- [ ] An unacted-on Question results in the Answerer being consulted
- [ ] An answer returned from the Answerer is sent into the session and appended to the Answer log
- [ ] An escalation returned from the Answerer notifies the operator and is recorded in the Answer log, and nothing is sent into the session
- [ ] A Question already acted on is not consulted twice
- [ ] The first consultation of a Run starts an Answerer session and records its identifier; every later one resumes it
- [ ] The Answerer runs against the target repository
- [ ] The Answerer's instructions state the authority boundary in terms of whether the answer is discoverable in the repository
- [ ] The Answer log shows each Question, its options, and the answer chosen, in the order they occurred
- [ ] Consultation and response rules tested as data in, Action out, with the Answerer's outcome supplied as a signal
