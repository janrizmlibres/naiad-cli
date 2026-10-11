# A Prompt is typed, never pasted

Most of the Workflow's Prompts open with a slash command, because the State's work is a skill's and a skill's logic belongs in the skill. Claude Code turns that opening into a skill invocation only for input the operator typed. Bracketed paste is not typed input: it arrives in the box as `[Pasted text #1 +3 lines]` and is submitted whole, as prose.

Naiad used to paste anything multi-line or past two hundred characters, which is every skill-invoking Prompt in the shipped Workflow. The failure is silent and it is worse than an error. The agent still reads `/implement the ticket at …` as the first line of its instructions, recognises the intent, and does something — for most skills it calls the skill itself, so the Workflow appears to run. For a skill marked `disable-model-invocation` it cannot, and instead improvises the whole State from the one line naming it. Nothing anywhere reports that the skill never ran.

So every Prompt is typed: each line with `send-keys -l`, and the newlines between them as Alt-Enter, which is the TUI's own "newline, don't send". There is no size threshold and no second path — a mechanism used only for long Prompts would be untested on exactly the Prompts that matter.

## Consequences

Naiad now depends on Alt-Enter inserting a newline and on typed input being parsed for commands. Both are operator-facing behaviour of the input box rather than internals, so this is the terminal surface ADR 0002 already accepts rather than a fourth coupling — but it is a narrower dependency than "send keys to a session", and it is the kind that would be reverted as a simplification by anyone who sees only that pasting is fewer calls. Hence this record.

What reaches the TUI is asserted as a list of tmux commands, in `keystrokes_for`. Reading the pane back to confirm a Prompt was typed rather than pasted is the one check that would answer the question directly, and it is precisely what ADR 0002 forbids; that a slash command actually dispatches is therefore verified by manual smoke.
