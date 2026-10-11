# The Answerer is opt-in and visible

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

Is the Answerer opt-in, and can an operator watch or take over a consultation? Today every Question goes to the Answerer unless the State declares `questions = "human"` (ADR 0046); there is no file-level default, so an author who wants no Answerer writes the key on every State. The Answerer is `claude -p` with `bypassPermissions`, a five-minute timeout, and an Answer log read afterwards. Decide: whether an absent `[answerer]` table means every Question is the human's; whether `questions` gains a file-level default a State overrides, like `model`; and what "not headless" means for an adopter who wants control, choosing between a consultation the operator can watch in its own tmux window and take over, an Answerer that proposes an answer the human confirms before it is sent, or the Answer log plus opt-in as enough. Record the default and its reasoning as an ADR amending 0046.

## Comments

2026-09-19, from "The starter workflow": the starter ships with no `[answerer]` table, so under the opt-in reading its Questions park the Run and the human answers in the Session. Two things this ticket has to keep: the `ask` verb survives without an Answerer, because the Protocol's reason for it ("no human is watching, so a prose question blocks forever") holds either way, so without an Answerer `naiad ask` behaves as a Reserved Question does today; and the Protocol text should stop describing an Answerer when none is declared, while still teaching `ask`.

2026-09-19, from "The verb surface": the user wants no Answerer by default, the `[answerer]` table and a per-State flag being the opt-in. That default is this ticket's to record, not the verb surface's. Whatever value set `questions` ends with, `naiad state set WF STATE questions VALUE` and `unset` ride it unchanged; the `add` flag takes its polarity from here: with the human as default, `add` carries an opt-in flag (the user's suggestion: `--auto`) and no `--questions human`.

## Answer

Resolved 2026-09-19 by grilling; recorded as [ADR 0050](../../../docs/adr/0050-a-question-is-the-humans-unless-the-workflow-says-otherwise.md), amending 0046.

- **The human is the default.** A Workflow with no `[answerer]` table gives every Question to the human: the Run parks as on an Escalation, the notification carries the Question's text, the human answers in the Session. The starter declares nothing, so every one of its Questions parks.
- **The table is the file-level default, not a new key.** Declaring `[answerer]` flips every State to the Answerer; a State overrides either way with `questions = "human"` or `questions = "answerer"`. A State opting in inside a table-less file gets the Answerer on the platform's default model and effort, as an empty table would. The table is never a precondition, so no verb refuses the flag. A separate top-level `questions` key is rejected.
- **Headless stays.** The watchable tmux consultation and the confirm-before-send draft are both rejected for this release; control is the default now, and the Answer log is the adopter's visibility. It must be readable without opening JSON: that is the new ticket "Reading a Run's Answers".
- **Reserved Question keeps its name** and widens to "a Question the Workflow gives the human". The log keeps the escalated flag; the reason gains a second wording, "no Answerer is declared", beside 0046's "state X reserves its Questions for you". Glossary updated.
- **The Protocol is unchanged.** It never names the Answerer; `naiad ask` survives without one because a prose question in an unwatched session blocks forever, and an `ask` wakes a person.
- **Verb polarity for "The verb surface":** `naiad state add --auto` writes `questions = "answerer"`; there is no human flag on `add`. `show` says whose a State's Questions are.
