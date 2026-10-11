# Output is styled for a person and left plain for an agent

Two audiences read what Naiad prints. An operator at a terminal reads it at a glance: a night of `queue watch` narration, the queue listing, the doctor's report. An agent's Bash tool and a hook read the same streams as text and match on their words. Until now everything was printed in one weight for both, and the operator paid for it: a parked Entry, a failure or a refusal sat level with every other line until it was read.

We decided:

- **Output a person reads is styled with `rich`, and only at a terminal.** Every Console is made in `naiad.cli.style`, at the moment of printing, and colours a stream only when it is a real terminal. `NO_COLOR` drops every style, `FORCE_COLOR` colours a pipe, and markup, highlighting and emoji codes are off, so `[bold]` in a Task is the operator's text. Styles are named for what they mean (`status.parked`, `refusal`), and the palette is kept in one place. Where nothing will be coloured, a line is printed with `print`, so it reaches the reader with every byte unchanged. A Console would turn a tab into spaces and drop a carriage return.
- **Text an agent or a hook reads keeps its words and its layout.** Colour is safe there, because it is decided by the stream and an agent's Bash tool is never a terminal. A change of layout is not, because it reaches every reader. So these are held to the exact text they had, with tests: `naiad states`, the Protocol verbs' replies (announce, ask, wait, hold, branch, spawn), `naiad adopt`'s teaching, the `queued` lines that `queue add`, adopt and spawn report through, the refusals of all of these, and everything a hook prints. `naiad states` is the reason this is a rule rather than care. The adopt skill parses its heading, its command column and its arrows, and a copy of the skill installed on a machine outlives the release that wrote it. A hook's output is plain everywhere, since it goes to Claude Code and not to a terminal.
- **Where the two audiences want different layouts, the layout is split, not compromised.** An author reads a Workflow's States as a table (`workflow show`, `state list`) built from the same facts as `naiad states`, which keeps its own lines.
- **`queue list` shows each Entry by a short id**: the fewest trailing parts of its id, counted at its dashes, that no other Entry's id ends in. `naiad queue rm` and `naiad queue answers` take it as well as the full id, and refuse one that has come to name several Entries, naming them.
- **`rich` is the second runtime dependency**, beside `tomlkit`.

## Considered options

**Write the escape codes by hand.** No new dependency, but a terminal check, `NO_COLOR` and `FORCE_COLOR`, widths measured in cells for wide characters, and cutting a styled cell with an ellipsis would all have to be written and tested here. `rich` already does each of these.

**A machine-readable flag on every command, styling the default freely.** The agents and skills already installed parse today's text and would not pass the flag, so the default would still have to keep its words.

**A full-screen picker for `naiad state next`.** `rich` draws no interactive picker, so this would still be a third dependency, and a numbered prompt is enough for a short list of names the author already knows.

## Consequences

A line built for the operator can be restyled freely. A line an agent reads can be recoloured, but its words and layout change only together with the skill or the Protocol that reads them. Only the terminal leg of a notification is styled. The desktop banner and the phone are handed the same plain title and message as before.
