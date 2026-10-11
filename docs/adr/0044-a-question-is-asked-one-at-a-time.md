# A Question is asked one at a time

Only the latest Announcement is kept, and for States that is right: an Announcement replaced before Naiad looks is stale intent the agent has already moved past. A Question is the case where that reasoning fails. An agent that computed a round of frontier questions and asked them all in one turn had each ask accepted, each one promised "the answer will arrive in this session" — and each write replaced the one before it, so every Question but the last vanished before any tick saw it, into no log anywhere, while the agent waited on answers that could never come. Five questions are five decisions the agent still wants; none of them is stale.

So a Question is asked one at a time. The ask command refuses while an unanswered Question stands, and a Question is unanswered until the Respond that sent its answer recorded its seq as handled, or the Answerer's Escalation resolved it onto a human. The refusal carries the protocol — hold the rest, ask again when the answer arrives — and the answer message closes by inviting the next question, so re-asking is triggered by each arrival rather than remembered across the wait. Announcing a State over an unanswered Question stays permitted, because abandoning its own Question is the agent's judgment (ADR 0001) — but it is recorded in the Answer log as an abandonment, since a log holding only the Questions that were settled would show an unattended Run as tidier than it was.

## Considered options

**One ask carrying the whole round** would let the Answerer see every question before answering any, which serialising forecloses — under this decision each Consultation answers blind to what is still coming, softened only by the resumed Answerer session remembering what it already said. It was rejected because a Question is one decision with its options, and a batch forces multiplicity through the Question, the Answer log, and the delivery — and needs a partial-escalation rule ("answered 1, 2 and 4; escalated 3") that exists only to serve the batching.

**Truly multiple pending Questions** — a list in the State file or beside it, each consulted and answered in turn — is most faithful to what agents naturally do. It was rejected because it dismantles the single-latest invariant and the per-Announcement keying of every record that hangs off it, to buy a behaviour the refusal gets for two sentences of error text.

## Consequences

A round of N questions costs N consult-and-respond cycles instead of one, which is minutes on an unattended Run and buys something back: the agent sees each answer before wording its next question, which is how an interview is supposed to run. The failure mode left is an agent that never re-asks what it held back — and that decays into ordinary silence, which the Wait expiry and the Nudges already answer, where the old failure was questions lost silently with the agent waiting forever on a promise.
