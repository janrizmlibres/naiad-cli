# 10 — Authoring tracer: `naiad workflow new`, `show`, `check`

Status: resolved
Mode: AFK
Blocked by: 01, 02, 03, 06
Spec: [PRD](../PRD.md), "Packaging, naming and license" (the TOML writer) and "The verb surface"

**What to build:** The first end-to-end authoring path, and the machinery every later authoring verb uses.

- **The writer.** A comment-preserving TOML writer (`tomlkit`, the one runtime dependency) behind a small edit-a-Workflow-file module. Every write is validated, written atomically, reloaded through the one load path, and the previous bytes are restored if the reload fails, then the loader's error is reported. Writes go through symlinks to their targets.
- **The renderer.** One renderer, shared by `workflow show` and the existing `naiad states`.
  - The kind column says what Naiad does on entry: `prompt`, `gate` or `terminal`.
  - The marks follow it: `→ a, b` for successors, `clears`, `report`, `questions: human|answerer` (resolved against the file's default), and the Model and Effort.
- **`naiad workflow new NAME`** writes `name` and a terminal `done` into the library, and refuses a name that exists.
- **`naiad workflow show WF`** prints the file-level keys, then the States through the renderer.
- **`naiad workflow check WF`** loads the file as a Run would, and prints the loader's refusal (exit 2) or a one-line OK (exit 0).
- `WF` is a library name or a path, by shape.

- [ ] `naiad workflow new demo`, then `show demo`, shows one terminal State. `check demo` passes, and `naiad queue add demo …` accepts it.
- [ ] A hand-edited file with comments keeps them byte-for-byte through a write-and-reload.
- [ ] A write the loader rejects leaves the file exactly as it was and prints the loader's error.
- [ ] A library entry that is a symlink is written through to its target.
- [ ] `naiad states` and `workflow show` render kinds and marks identically.
- [ ] Built test-first, Refactor verdict recorded.

## Comments

Refactor verdict (commits 6d6d59d, 6b50559). Candidates considered:

- `_states`, `workflow show` and `workflow check` each loaded a Workflow and printed a refusal: extracted `_print_workflow`, one load-and-refuse path for all three.
- `render_states` and `render_workflow` shared the State lines: extracted `_state_lines`, so the two readers cannot render a mark differently.
- `scaffold_workflow` and `edit_workflow` both write then load: keep separate. A scaffold has no previous bytes to restore, so a shared tail would carry a branch only one caller takes.
- `_line` takes five width and cell parameters, a possible Data Clump: keep, the scope is one private function.
- `_kind` returns a string that `_marks` compares: keep, a `State.kind` would be a new domain concept no other code needs yet.
- `edit_workflow` has no verb calling it yet: keep, the ticket names it as the machinery every later authoring verb uses, and its tests pin the contract.

Code review found the writer resetting a hand-edited file to 0600 and Terminal and Gate States printing the file's Model; both fixed test-first in 6b50559.
