# The maintainer's record is public

Supersedes ADR 0054.

ADR 0054 kept the maintainer's record (`docs/adr/`, `CONTEXT.md`, `docs/agents/`, `docs/maintainer/` and `.scratch/`) out of the public repository through `.git/info/exclude`, with the Agent-skills setup block in an untracked `CLAUDE.local.md`. The maintainer reversed that on 2026-10-11: the Agent skills' files are kept in their default, tracked layout in every personal repository, and Naiad's go public with them.

We decided the record is tracked and pushed with the code:

- `docs/adr/`, `CONTEXT.md`, `docs/agents/` and `docs/maintainer/` are committed.
- `.scratch/` is committed for its markdown only. `.gitignore` names `.scratch/**` and lets its directories and `*.md` files back in, so the tickets, specs and maps are tracked and the run logs, wheels and scripts left there stay on disk.
- The Agent-skills setup block lives in `AGENTS.md`, and `CLAUDE.local.md` is gone.

The rest of ADR 0054 lapses with it. The release no longer rewrites history with `git filter-repo` or recreates the GitHub repository, and tracked text may cite an ADR, a ticket or the glossary again. Citations already rewritten to state their rule inline stay as they are.

## Considered options

**Keep ADR 0054.** It hid the maintainer's working notes from adopters, but it left the record with no remote and no backup, and every new clone without it until the excludes were set up again.

**Track `.scratch/` whole.** Rejected: it holds build artefacts and logs that are not part of the record.

## Consequences

ADR 0054's name and the PyPI decisions in it still stand: the repository and the distribution are `naiad-cli`, and the command is `naiad`. Its contribution terms stand too.
