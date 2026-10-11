# The public repository

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

What is the public repository, and what in this one is public? Decide: the repository's name (`naiad-v2` is a working name) and whether the history ships or the release starts a fresh history; whether the `.scratch/` tracker, `docs/agents/`, `docs/adr/`, `CONTEXT.md` and `AGENTS.md` are public as they stand, moved, or explained in a contributor note; whether contributions are accepted at all at the first release, and if so with what expectation (ADRs, CONTEXT.md, the tracker conventions); and the PyPI name: `naiad` is taken by an empty 2016 project (see the resolved Publishing to PyPI ticket), so decide between filing a PEP 541 transfer request, publishing under a fallback such as `naiad-cli`, or both in sequence, and whether the PyPI and repository names must match.

2026-09-24, from "The license": the holder line is `Copyright (c) 2026 Janriz Libres` for now. If contributions are accepted, decide whether they come in under the same license, with no CLA, and whether the line becomes "Janriz Libres and contributors".

2026-09-24, from "What becomes of the personal workflow": direction decided by the human — adopters should not see the maintainer artifacts. `docs/adr/`, `CONTEXT.md`, `docs/agents/` and `.scratch/` go untracked, in the setup's untracked mode (`~/.claude/reference/matt-pocock-untracked.md`), and come off the remote. Facts this ticket starts from:
- The remote `janrizmlibres/naiad-cli` is already **public**, and all of the above is committed and pushed today (the setup ran in committed mode). Untracking removes them from the tip only; every past commit still carries them, so "not seen" needs a history rewrite or a fresh history for the release — this ticket's history question now has a constraint.
- Tracked code and tests cite ADRs about 490 times across `naiad/` and `tests/`, plus `README.md`, `AGENTS.md`, `docs/workflow-authoring.md` and `docs/smoke/matt-pocock.md`. The global rule forbids tracked text citing untracked docs, so each citation is rewritten to state its rule inline.
- The human said "gitignored"; the untracked-mode reference says `.git/info/exclude`, never `.gitignore`, because a checked-in `.gitignore` names what is hidden. Settle which.
- `AGENTS.md`'s `## Agent skills` block is setup scaffolding; untracked mode moves it to `~/.claude/context/naiad-v2.md` via an untracked `CLAUDE.local.md`, and its "Workflow files" section cites `docs/adr/`.
- `docs/smoke/` is not in the reference's exclude list but is maintainer-only (the personal Workflow's smoke goes untracked per the resolved ticket); decide whether the whole directory follows.

## Answer

2026-09-26, grilled with the human. Recorded as ADR 0054.

- **Names**: the repository and the PyPI distribution are both `naiad-cli`, and the command stays `naiad`. No PEP 541 request. `pyproject.toml`'s `name` becomes `naiad-cli`, and install is `uv tool install naiad-cli`. (`naiad-cli` was free on PyPI on 2026-09-24.)
- **Visibility now**: the repository stays public until release. Going private in the meantime was considered and dropped: the repo has no stars or forks, a private flip cannot take back what was already seen, and only the delete-and-recreate at release removes the history.
- **History**: kept and filtered at release, the step before the first `uv publish`. `git filter-repo` removes `docs/adr/`, `CONTEXT.md`, `docs/agents/`, `docs/smoke/` and `.scratch/` from every commit, which drops 14 commits that touched nothing else. A message callback rewords every commit message to make its point without citing an ADR, ticket, glossary or `.scratch` (219 message lines cite them today). An agent drafts the rewordings and the human reviews them. Past file contents are left as they were. The GitHub repository is deleted and recreated, and the filtered history is pushed, because a force-push leaves the old commits reachable by SHA. The local-only `research/*`, `prototype/*` and `worktree-agent-*` branches are dropped then too, since the spec will have absorbed them.
- **Maintainer artifacts**: the five paths above plus `CLAUDE.local.md` are hidden through `.git/info/exclude`, never `.gitignore`, and live only on the maintainer's laptop, with no private repository, backup or bundle. `docs/smoke/` goes whole.
- **Citations**: every tracked ADR citation (about 490 in `naiad/` and `tests/`, plus `README.md`, `AGENTS.md` and `docs/workflow-authoring.md`) is rewritten to state its rule inline.
- **`AGENTS.md`**: stays tracked, holding the Workflow-files rule restated with no ADR pointer, plus whatever contributor rules apply. The `## Agent skills` block moves to `~/.claude/context/naiad-v2.md`, loaded through an untracked `CLAUDE.local.md`.
- **Contributions**: accepted, with GitHub Issues open. A short `CONTRIBUTING.md` asks for an issue before a non-trivial PR and for tests first and passing. Contributions come in under the outbound licenses (MIT and 0BSD) with no CLA. The holder line stays `Copyright (c) 2026 Janriz Libres`.
- **Handed on**: the per-State ADR index in `docs/workflow-authoring.md`, and where `CONTRIBUTING.md` sits in the set, go to "The documentation set".
