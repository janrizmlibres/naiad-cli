# 19 — Untrack the maintainer's record

Status: resolved
Mode: HITL
Blocked by: 15, 17, 18
Spec: [PRD](../PRD.md), "The maintainer's record and the history"; ADR 0054

**What to build:** The public tip holds no maintainer record.

- `docs/adr/`, `CONTEXT.md`, `docs/agents/`, `docs/maintainer/`, `.scratch/` and `CLAUDE.local.md` are listed in `.git/info/exclude`, never `.gitignore`, and removed from the index while staying on disk.
- `docs/smoke/` is already renamed `docs/maintainer/`.
- `AGENTS.md`'s Agent-skills block moves to `~/.claude/context/naiad-v2.md`, loaded through an untracked `CLAUDE.local.md`, following the untracked-mode reference.

HITL because it rewrites what git tracks and the maintainer's own Claude configuration.

- [x] `git ls-files` lists none of the six paths, and they are still readable on disk.
- [x] A fresh agent session in the checkout still loads the Agent-skills setup through `CLAUDE.local.md`.
- [x] No tracked file cites any of the six paths: grep over `git ls-files` is clean.

## Comments

2026-09-29 — Excludes written to `.git/info/exclude`; the five tracked paths removed from the index (120 staged deletions, uncommitted), all six still on disk. `AGENTS.md` trimmed to Workflow files; the Agent-skills block now lives in `~/.claude/context/naiad-v2.md`, imported by `CLAUDE.local.md`. Grep over `git ls-files` for the six paths (and `docs/smoke`) is clean; 1518 tests pass.

Open: a headless `claude -p` session sees `CLAUDE.local.md` but not the import, because this project has not yet approved external `@` imports (`hasClaudeMdExternalIncludesApproved: false`). The next interactive session prompts for it once; after approving, the second criterion can be ticked and the ticket resolved.

2026-09-29 — External imports approved; a fresh headless session now answers the tracker and triage-label questions from the imported block. All three criteria met; resolved.
