# The verb surface

Type: prototype
Mode: HITL
Status: resolved
Blocked by: 02

## Question

Does the authoring verb surface feel right in the hand? Stub the argparse tree for `naiad workflow list|show|new|rm|check` and `naiad state list|show|add|rm|set|move|set-prompt`, with help text only and no behaviour, and react to `--help` output and to a scripted authoring session (new workflow, three States, one Gate, one branching State, a Prompt from a file). Decide: the exact arguments and flags of each verb; how `show` and `list` name a State's kind; and how every key at both levels is reached. File-level keys today: `name`, `model`, `effort`, `autocompact`, and the `[answerer]` table's `model`, `effort`, `fallback`. State-level keys: `name`, `prompt`, `clear`, `terminal`, `next`, `model`, `effort`, `questions`. Prefer one generic `naiad workflow set <key> <value>` and `naiad state set <workflow> <state> <key> <value>` whose key set is read from the parser rather than a verb per key, so keys other tickets add (a notify-on-entry key, a file-level `questions` default, whatever the configuration ticket promotes) ride it without a new verb; then decide which keys still deserve a verb of their own (`set-prompt` for the editor, rename for its edge rewriting, `next` for its list shape), whether `terminal` is settable at all or only scaffolded, and what `naiad workflow new` scaffolds beyond the terminal `done`.

## Answer

Resolved 2026-09-19 by a prototype and three grilling rounds. The stub is `naiad/cli/_prototype_verb_surface.py` on branch `prototype/verb-surface` (`uv run python naiad/cli/_prototype_verb_surface.py tour|session`). One standing decision in the map's Notes is amended: the Protocol's announce verb leaves `naiad state`.

### The decision

1. **`naiad announce STATE [--subject S]` replaces `naiad state STATE`.** The Protocol teaches the verb in every fresh context, so the rename costs the agent nothing; `naiad state` becomes the authoring noun with no reserved State names and a plain argparse tree. Rejected: keeping both under `state` with a first-word dispatch and ten reserved names; nesting authoring as `naiad workflow state …`.
2. **The tree.** `naiad workflow list | show WF | new NAME [--from WF] | rm WF | rename WF NEW | check WF | set WF KEY VALUE | unset WF KEY` and `naiad state list WF | show WF STATE | add WF STATE | rm WF STATE | rename WF STATE NEW | set WF STATE KEY VALUE | unset WF STATE KEY | move WF STATE (--after|--before STATE) | next WF STATE [STATE ...] [--none] | set-prompt WF STATE`. `WF` is a library name or a path, by shape (ADR 0023).
3. **Generic `set` and `unset`, keys read from a table.** File level: `model`, `effort`, `autocompact`, `answerer.model`, `answerer.effort`, `answerer.fallback`. State level: `model`, `effort`, `clear`, `terminal`, `questions`. `--help` prints the table with each key's value shape; a key another ticket adds rides both verbs. `unset` deletes the key, because absence is an opinion of its own (ADR 0040). Values are validated from the table before any write; the reload-and-rollback after writing is the backstop.
4. **Verb-owned keys, refused by `set` with the verb named:** `name` (rename, at both levels: file and key move together, `next` edges rewritten), `prompt` (`set-prompt`), `next` (the `next` verb).
5. **Kind in `list` and `show`.** Kinds are not exclusive (`review` in the personal file is a Gate that branches), so one column says what Naiad does on entry, `prompt`, `gate` or `terminal`, and marks follow: `→ a, b` for successors, `clears`, `questions: human`, `model/effort`. `naiad states` moves onto the same renderer. `workflow show` adds the file-level keys above the States; `state show` adds the Prompt in full.
6. **`add`.** Lands before the terminal State unless `--after`/`--before`; `--terminal` lands at the end and implies no Prompt. Prompt sources, mutually exclusive: `$VISUAL` then `$EDITOR` by default, `--from FILE`, `--from -`, `--prompt TEXT`, `--gate`. No editor set is refused in one sentence naming both remedies (set EDITOR or pass --from). An editor that exits with an empty file changes nothing and says so. `--clear`, `--model`, `--effort` and `--next` write their keys; keys not given are absent.
7. **Order is the declared order.** A State without `next` hands over to the State declared after it and Gate skipping walks that order (ADR 0007), so `add --after/--before` and `move` edit the path most States take and `next` edits the exceptions.
8. **`next`.** Space-separated successors replace the list; `--none` clears it; no successors opens a numbered stdlib prompt listing the States with the current successors marked, refused outside a terminal with the list form named. No arrow-key picker and no dependency in this release; the picker exists on `next` only.
9. **`terminal` is settable** (`set terminal true|false`, `add --terminal`); a write leaving no terminal State is refused.
10. **`workflow new` scaffolds `name` and a terminal `done`, nothing else.** `--from` copies a name or path and rewrites `name` to the new stem.
11. **`rm` and `rename` on a workflow in use refuse and name the Entry or Run; no `--force`.** The remedy is `naiad queue rm`.
12. **The `questions` polarity follows "The Answerer is opt-in and visible".** `set questions VALUE` and `unset questions` ride whatever value set that ticket picks; if the default becomes the human, the `add` flag is the opt-in (something like `--auto`) and `--questions human` does not exist. A comment there records it.

### Considered and rejected

- Comma-joined successors (`implement,done`): fine, but positionals are what a shell user expects, tab-complete per word, and `ask --option` already repeats a flag rather than joining.
- `set KEY ""` as the way to remove a key: an empty string is a value, not an absence.
- A picker for `move --after` or `--questions`: each is one word the author already knows.
- Falling back to `vi` when no editor is set: the classic trap; a refusal is the house style.

## Comments

2026-09-19, from "Where shipped and authored workflows live": the library is a store of regular files the adopter owns, the starter included (`naiad install --starter` copies it; nothing is symlinked by Naiad). Consequences for the surface: no verb refuses an entry for being a symlink, they write through hand-made links; `naiad workflow rename <old> <new>` is decided to exist, moving the file and its `name` key together and refusing while a queued Entry or live Run addresses the file, its exact arguments are this ticket's; `naiad workflow new <name> --from <name-or-path>` copies and rewrites `name` to the new stem.

2026-09-19, from "The Answerer is opt-in and visible": polarity settled. The human is the default, so `naiad state add --auto` writes `questions = "answerer"` and there is no `--questions human` on `add`; `set`/`unset` ride the key. The `[answerer]` table flips the file default, so `show` must say whose a State's Questions are rather than print the key alone (ADR 0050).
