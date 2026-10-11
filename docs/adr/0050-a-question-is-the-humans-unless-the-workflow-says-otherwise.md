# A Question is the human's unless the Workflow says otherwise

ADR 0046 let a State reserve its Questions for the human with `questions = "human"`, and made absence mean the Answerer, because every State meant that before the key existed. That default was the maintainer's: one Workflow, one operator, an `[answerer]` table always declared. An adopter installing the starter has declared nothing, and under 0046 their first `naiad ask` would spawn a headless Claude session with `bypassPermissions` in their repository and act on what it said, with the Answer log the only witness. An author who wanted no Answerer had to write the key on every State.

We decided the human is the default. A Workflow with no `[answerer]` table gives every Question to the human: the Run parks as on an Escalation, the notification carries the Question's text, and the human answers in the Session. Declaring the table flips the file default, so every State consults the Answerer unless it says `questions = "human"`. The opposite override works too: a State in a table-less file may say `questions = "answerer"`, and the Answerer runs for that State on the platform's default model and effort, exactly as an empty `[answerer]` table would run it. The table is never required for the Answerer to exist; it carries its settings and moves the default.

## The table is the file-level default

0046 asked whether `questions` should gain a file-level default a State overrides, as `model` has. It does not need a key of its own: the presence of the `[answerer]` table is that default. An author turns the Answerer on in one place, and an author who wants human-by-default with an Answerer declared writes `questions = "human"` on the States that matter. A separate top-level `questions` key was rejected because it would make one fact expressible two ways; if the pattern it serves shows up in real Workflows, it is a one-line addition later.

The `questions` enum keeps its two members. What moves is the State's default, which the loader takes from the table's presence rather than from a constant.

## A Reserved Question is now the ordinary case

The glossary's Reserved Question was the exception: a Question a State kept from the Answerer. It keeps its name and widens: a Question the Workflow gives the human, which is every Question unless the State or the table says otherwise. The mechanism is untouched, because 0046 already routed it down the Escalation's road and nothing there depended on it being rare. The Answer log keeps recording it as escalated (0046 rejected a third flag, and the reason still names who woke the human) and the reason gains a second wording: "no Answerer is declared" where no table and no State key put the Question with the human, and 0046's "state X reserves its Questions for you" where a State did. The notification says the same before the Question's text.

## The agent's side is unchanged

The Protocol does not name the Answerer. It says never ask a human directly, run `naiad ask`, and the answer comes back into this session; that is true whether a headless session or a person typing in the Session supplies it. So `ask` survives a Workflow with no Answerer for the reason the Protocol gives: no human is watching the session, and a prose question would block forever, while an `ask` parks the Run and wakes one. Without an Answerer, `naiad ask` behaves as a Reserved Question did under 0046.

## Headless stays, and the log is the visibility

The ticket asked what "not headless" means for an adopter who wants control, and weighed a consultation the operator watches in a tmux window and can take over, and an Answerer whose draft the human confirms before it is sent. Both are rejected for this release. Control is now the default: the Answerer runs only where a Workflow asks for it, and an adopter who turns it on has chosen to trust it. A watchable consultation needs a second session adapter and a reply channel that is not stdout, against ADR 0002's rule that a reply is a value rather than pixels. A confirmed draft is the human default with a headless call in front of it. What the adopter is owed instead is the Answer log, readable without opening JSON; that is a ticket of its own.

## Considered alternatives

**Table and flag both required**, so a State consults only when the table exists and the State says `questions = "answerer"`. Rejected: an author with an Answerer would write the key on every State, the burden 0046's default imposed, inverted.

**The loader refusing `questions = "answerer"` without a table.** Rejected: it makes the Answerer's existence depend on a settings table, and `naiad state add --auto` would have to refuse in a fresh Workflow.

**A file-level `questions` key.** Rejected above.

## Consequences

`State.questions` no longer defaults to a constant; the loader gives it `"answerer"` when the file declares `[answerer]` and `"human"` otherwise, before the State's own key. The shipped starter declares no table and no key, so every one of its Questions parks the Run. The shipped Wayfinder Workflow keeps its table and its `questions = "human"` on `wayfind`, and means what it meant.

`naiad state add` carries an opt-in flag (`--auto`) that writes `questions = "answerer"`, and no flag for the human; `set` and `unset` ride the key unchanged. `naiad workflow show` and `naiad state show` say whose a State's Questions are, since the answer now depends on the file.

The Reserved Question's glossary entry, the reason wording in the decision function, and `docs/workflow-authoring.md`'s account of the `[answerer]` table follow.
