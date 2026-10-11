# 12 — The `naiad state` verbs

Status: resolved
Mode: AFK
Blocked by: 10
Spec: [PRD](../PRD.md), "The verb surface"; map ticket [03](../issues/03-the-verb-surface.md); help-wording fixture on branch `prototype/verb-surface`

**What to build:** Authoring a Workflow's States without leaving the shell.

- **`list WF`** and **`show WF STATE`** go through the shared renderer. `show` adds the Prompt in full.
- **`add WF STATE`**:
  - Placement: before the first terminal State unless `--after` or `--before`; `--terminal` lands it at the end with no Prompt.
  - Prompt source, mutually exclusive: `$VISUAL` then `$EDITOR` by default, `--from FILE`, `--from -`, `--prompt TEXT`, or `--gate`.
  - With no editor set, it refuses in one sentence naming both remedies. An empty editor buffer changes nothing and says so.
  - `--clear`, `--model`, `--effort`, repeatable `--next`, `--terminal` and `--auto` write their keys. `--auto` writes `questions = "answerer"`, and there is no human flag.
- **`set-prompt WF STATE`** takes the same Prompt sources as `add`, and writes a multi-line Prompt as a multi-line string.
- **`set WF STATE KEY VALUE`** and **`unset WF STATE KEY`** work over the State key table: `model`, `effort`, `clear`, `terminal`, `questions`, `report`. `set` refuses `name`, `prompt` and `next`, naming `rename`, `set-prompt` and `next`.
- **`rename WF STATE NEW`** rewrites every `next` edge naming the State.
- **`rm WF STATE`** refuses while another State names it in `next`, naming those States.
- **`move WF STATE --after|--before OTHER`** reorders States.
- **`next WF STATE [STATE …]`** replaces the successors, and `--none` clears them. With no arguments it opens a numbered standard-library picker with the current successors marked, and refuses outside a terminal, naming the list form.
- Any write that leaves no terminal State is refused.

- [ ] A scripted session builds a Workflow with three Prompt States, one Gate, one branching State and a Prompt from a file, and `workflow check` passes.
- [ ] `add` lands before `done` by default and honours `--after`, `--before` and `--terminal`.
- [ ] Each Prompt source works. A missing editor and an empty buffer behave as specified, with a fake `$EDITOR` script.
- [ ] `rename` rewrites edges; `rm` of a named successor is refused, naming the States.
- [ ] `next` with no arguments and no terminal refuses; `--none` clears.
- [ ] Unsetting the last `terminal` is refused.
- [ ] Built test-first, Refactor verdict recorded.

## Comments

Refactor verdict (commit 2f92d56). Candidates considered:

- `state.py` resolved the file path the same way in five handlers and worked out a State's position twice: extracted `_path` and `_position`.
- `key_table.py` had a `set` check and an `unset` lookup per level: folded into one `_Level` table and one `_one_line` path, so the file and State keys share the refusals.
- Code review found `add --model` and `--effort` bypassing the key table, so `add --model ''` wrote an empty key that `set` refuses; fixed test-first by routing them through `state_value`.
- `state.py` has its own `_refusing` guard where `main.py` repeats a try/except in each `workflow` handler: keep, converting the existing handlers is outside this ticket.
- `add_state` takes eleven parameters, `after`/`before` travelling together as a possible Data Clump: keep, they are one argparse group at the boundary and a type for them would be used in two places.
- `_put` here and `_insert_file_key` in `workflow_file.py` both wrap a tomlkit private insert: keep, the anchors differ (last key of a State, last file-level key) and each has its own test pinning the placement.
- `require_state` and `check_placeable` read a `Workflow` in a module of document edits: keep, they exist so an editor session is not opened for a State the file cannot take.

Known and left: a comment written between two States belongs to the State above it in the writer's model, so `state move` carries it with that State, and a State added ahead of one leaves the comment above the new State. `--terminal` still takes `--next`, `--clear` and `--auto`, and `set-prompt` on a terminal State is accepted; the ticket says neither.
