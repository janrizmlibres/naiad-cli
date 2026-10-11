# A Prompt is typed in pieces and confirmed whole

A Run reached `pull-request` and its agent received that State's Prompt with the first 1022 bytes gone: it began mid-word, `ompanion none of whose branches…`, and the paragraph telling the agent how to find the companion repositories was never read. Nothing noticed. The Prompt was submitted, a Turn began, the Stop hook fired when it ended, and the Run carried on as if the State had been given what its Workflow says.

It looked like ADR 0038's race, since the Prompt followed an `/effort` by one Tick. It was not. Probed against the live TUI, a single write of about a kilobyte or more is read by the Session as a paste whatever came before it. Some arrive wrapped as pasted content. Others lose exactly their first 1022 bytes. The same long line typed into an idle Session, with no slash command ahead of it, lost the same 1022 bytes. The tmux adapter types each line of a Prompt as one `send-keys`, and the `pull-request` Prompt is the only shipped one with a line over that size (1243 bytes). So every delivery of it has been cut.

Two changes follow. One removes the cause, and the other makes sure the next cause of this kind is loud.

**A line is typed in pieces.** No single `send-keys` carries more than 256 bytes, and a piece is cut between characters, never through one. Pieces of 500 bytes arrived whole in the probe and pieces of 1000 did not. 256 leaves a margin below both, and the cost is a few more tmux calls per Prompt.

**A Prompt is confirmed, as a Clear is (ADR 0019).** Before typing, the loop records the rendered Prompt, its attempt number and when it was typed. A `UserPromptSubmit` hook, installed beside the other two, judges every prompt submitted in a Run's Session against it:

- A prompt that is the Prompt, compared with whitespace collapsed, has **landed**. The hook lets it through and records that.
- A prompt that is not the Prompt, submitted within the confirm window of the typing, was **turned away**. The hook exits 2, which blocks the prompt and erases it before the agent sees any of it.
- Anything else passes untouched. That covers a human's prompt between deliveries, a mismatch after the window has passed, and a session no Run is driving.

The decision then reads the verdict. A landing is a `Confirm`, which marks the Announcement handled, so typing a Prompt no longer counts as delivering it. A rejection is typed again on the next Tick, because a blocked prompt proves the Session is idle and took none of it. The number of attempts is bounded, and past the bound the human is told.

A Prompt the hook said nothing about is **not** typed again. Silence is also what a hook that was never installed produces, while the agent works on a Prompt that arrived fine. A retype would queue a second copy behind that agent. So silence past the window tells the human, and the message names `naiad install` as a likely fix. A rejection is the only evidence strong enough to type over.

## Considered options

**Pieces alone**, with no confirmation, fixes the failure that was found. It was rejected because it rests on a threshold measured once against one version of the TUI, and the failure it guards against is the silent kind. ADR 0038 accepted a dropped Prompt without confirmation because a Prompt that never arrives starts no Turn, so the Run parks where a human sees it. A Prompt that arrives cut short starts a Turn, and nothing parks. ADR 0019 bought confirmation for the Clear on exactly that ground: delivering into a Session that took something other than what was sent.

**Parking on a mismatch instead of retyping** is simpler and just as loud. It was rejected because an overnight Run would sit until morning over something a retype fixes.

**Rewriting the submission in the hook**, replacing a cut-short prompt with the Prompt Naiad typed, would save the retype. It was rejected because a Prompt that opens with a skill runs as one only when it arrives as typed input, and whether a rewritten prompt is still expanded as a skill is not documented.

**Confirming every send**, including Answers and Nudges, would guard them too. It was rejected for now because neither follows a slash command or carries a line near the size that fails, and each would need a retry rule of its own. The mechanism extends to them if one is ever seen cut.

## Consequences

Naiad now depends on three hooks, and an operator who upgrades without running `naiad install` again is told at every delivery that the Prompt was never reported. That is loud, and it does no damage, which is the trade ADR 0019 already made for the Clear.

A delivery costs one more Tick, the one that turns the hook's report into a `Confirm`. The Run log gains a `confirmed` line after each `delivered`, and a retype shows as `delivered … attempt 2`. `opened` now reads a `confirmed` line, so an Adoption's opening Prompt that never landed stays owed. A Run adopted before this change and still in its first State when the Supervisor restarts has no such line, and would be typed its opening Prompt again.

The threshold is a probe result, not a documented limit, and it can move with the TUI. The confirmation is what makes a move visible: a line the Session starts reading as a paste again is turned away, typed again, and after that reported to the human.
