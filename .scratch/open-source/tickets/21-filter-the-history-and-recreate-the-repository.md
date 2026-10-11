# 21 — Filter the history and recreate the public repository

Status: resolved
Mode: HITL
Blocked by: 19, 20
Spec: [PRD](../PRD.md), "The maintainer's record and the history"; ADR 0054

**What to build:** The public history holds no maintainer record.

1. Back up the local checkout, including the untracked record, before anything is rewritten.
2. `git filter-repo` removes `docs/adr/`, `CONTEXT.md`, `docs/agents/`, `docs/smoke/`, `docs/maintainer/` and `.scratch/` from every commit. Commits that touched nothing else drop out.
3. A message callback rewords every commit message to make its point without citing an ADR, a ticket, the glossary or `.scratch`. An agent drafts the rewordings as a reviewable mapping, and the maintainer approves them before the rewrite runs. Past file contents are left as they were.
4. Drop the local `research/*`, `prototype/*` and `worktree-agent-*` branches.
5. Delete the GitHub repository `naiad-cli`, recreate it public, and push the filtered `main`, because after a force-push GitHub still serves old commits by SHA.
6. Restore the untracked record into the new checkout and re-apply `.git/info/exclude`.

- [x] `git log --all -- docs/adr CONTEXT.md .scratch docs/agents docs/smoke docs/maintainer` is empty on the pushed repository.
- [x] No commit message on `main` cites an ADR, a ticket, the glossary or `.scratch`.
- [x] The maintainer's local record is intact and still excluded.

## Answer

Done 2026-09-30.

- Backup of the whole checkout, `.git` and record included, at `~/naiad-v2-backup-20260930.tar.gz`.
- `feat/open-source-release` fast-forwarded into `main`; a fresh clone filtered with `git filter-repo` on the six record paths, with a commit callback swapping in 66 reworded messages (the draft pass for citations plus a pass removing the former employer's names). Mapping, `review.diff` and `reword.py` in `rewrite/`. The maintainer approved the mapping.
- Employer names at the tip: test fixtures renamed in "Test fixtures name their branches and tasks generically". Past file contents left as they were.
- `janrizmlibres/naiad-cli` deleted, recreated public, filtered `main` pushed: 103 commits, tip tree `efbd894`. Checked on a fresh clone of the pushed repo: no commit touches the record paths, no message cites the record or names the employer.
- This checkout reset onto the new `origin/main`; `feat/open-source-release`, `prototype/*`, `research/*` and `worktree-agent-*` dropped, reflogs expired, gc run. The record and `.git/info/exclude` were never moved and stay untracked.
- `fix/pull-request-opens-the-working-branch` (another worktree) rebased onto the new `main`.
