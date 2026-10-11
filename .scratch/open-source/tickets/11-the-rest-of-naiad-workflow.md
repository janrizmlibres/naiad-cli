# 11 — The rest of `naiad workflow`

Status: resolved
Mode: AFK
Blocked by: 10
Spec: [PRD](../PRD.md), "The verb surface"; map tickets [02](../issues/02-where-shipped-and-authored-workflows-live.md), [03](../issues/03-the-verb-surface.md)

**What to build:** The remaining `naiad workflow` verbs.

- **`list`** shows every library entry, naming a broken link as broken.
- **`set WF KEY VALUE`** and **`unset WF KEY`** work over the file-level key table: `model`, `effort`, `autocompact`, `answerer.model`, `answerer.effort`, `answerer.fallback`.
  - `--help` prints the table with each key's value shape.
  - Values are validated before any write, and `unset` deletes the key.
  - `set name` is refused, naming `naiad workflow rename`.
- **`new NAME --from WF`** copies a name or a path and rewrites `name` to the new stem.
- **`rm WF`** and **`rename WF NEW`** refuse while an Entry that is not done, or a live Run, addresses the file, naming each. Paths are compared after resolving, so a link and its target count as one. `rename` moves the file and its `name` key together. There is no `--force`.

- [ ] Each file-level key can be set, shown and unset; an invalid value is refused before writing.
- [ ] `new b --from a` yields a file named `b` that declares `name = "b"` and resolves by name.
- [ ] `rm` and `rename` refuse while a waiting Entry addresses the file, naming it, and succeed once it is removed.
- [ ] A renamed Workflow resolves by its new name, and its old name is gone.
- [ ] Built test-first, Refactor verdict recorded.
