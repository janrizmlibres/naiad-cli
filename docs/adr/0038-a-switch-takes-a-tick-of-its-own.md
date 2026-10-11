# A Switch takes a Tick of its own

> Amended by ADR 0039. The cut-short Prompt later blamed on this race was the Session reading a long line as a paste; see ADR 0053.

ADR 0026 had the Model and Effort switches ride Prompt delivery, "each switch as its own send", and priced the pair at two keystroke lines. The price was wrong. Claude Code's TUI discards whatever arrives while it is handling a slash command it has already been given, so of `/model`, `/effort` and the Prompt typed back to back, one is swallowed and never reaches the input box. `/effort` lost every time, because it went second — the shipped Workflow ran every State at whatever effort the session happened to hold. Typing all three again on the next delivery heals nothing, because the retype loses one too.

So a Switch stops riding the Prompt and becomes an Action of its own, one to a Tick: `/model` on one Tick, `/effort` on the next, the Prompt on the one after. The Tick interval is already 2.0s, which a probe against the live TUI showed is enough where zero is not. Nothing is confirmed and nothing is re-typed within an Announcement — the spacing does the work a confirmation would have done, and ADR 0026's best-effort switch is untouched in every other respect. How far the sequence has got is a per-Announcement Signal beside the Clear's, so the next Announcement re-arms it and every delivery types the State's settings again, exactly as ADR 0026 intended.

The severe failure this closes is not the one it was found by. A Switch that is dropped costs a State the wrong price or quality, which ADR 0026 accepted knowingly. A **Prompt** that is dropped starts no Turn, so no `Stop` hook fires, so the silence rule never runs — it falls through to the hang rule and parks the Run for a human. On the unattended overnight Run that ADR 0026 exists to serve, that is the Run dead until morning. Before ADR 0026 there was no slash command ahead of a Prompt to race with, so the Prompt was safe; putting the switches there took that away without anyone noticing, and the sequence gives it back.

## Considered options

A fixed pause between the sends was the smallest change and is what the probe used to prove the diagnosis. It was rejected as the shape rather than as the delay: the Supervisor drives every Lane from one thread, so a sleep inside one Run's delivery stalls all of them, and a pause is the guess ADR 0019 already refused for the Clear.

Confirming the Prompt with a `UserPromptSubmit` hook, the way `SessionStart` confirms a Clear, would close the failure completely rather than making it unlikely. It was rejected as more machinery than the fault deserves: ADR 0019 bought confirmation for corruption — a Prompt delivered into a context that should have been discarded — where this fault ends in a park, which is loud and which a human sees. It stays available if the spacing ever proves not to be enough.

## Consequences

A delivery now costs about four seconds more than it did, which is nothing beside the phases it opens, and a Workflow file naming neither key spends no extra Tick at all. The Run log gains a `switched` line per Switch, which is the only record that one was typed, since none is confirmed.

The fix rests on `TICK_SECONDS`. The probe proved 2.0s works and 0s fails; the ground between them was not bisected, so lowering the interval would weaken the fix quietly rather than loudly. That is the standing caveat, and it is why the smoke criteria now ask that both Switches be seen ahead of a State's Prompt: no automated test can see this failure, because the fault is in a terminal that the test suite replaces with a fake which accepts every send.
