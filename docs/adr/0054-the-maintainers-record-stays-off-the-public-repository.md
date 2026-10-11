# The maintainer's record stays off the public repository

> Superseded by ADR 0068.

Naiad's decisions, glossary and tickets were committed alongside its code: `docs/adr/`, `CONTEXT.md`, `docs/agents/`, `docs/smoke/` and `.scratch/`. The repository `janrizmlibres/naiad-cli` is public. An adopter who installs Naiad should find a CLI, its documentation and its code, not the maintainer's working notes, and tracked code cited those notes about 490 times.

We decided the maintainer's record is untracked. It is hidden through `.git/info/exclude`, never `.gitignore`, since a checked-in `.gitignore` would itself name what is hidden. It lives only in the maintainer's checkout, with no private remote and no backup repository. Tracked text never cites it, so each citation in code, tests and documents is rewritten to state its rule inline. `AGENTS.md` stays tracked and keeps only rules a contributor can follow without the record. The Agent-skills setup block moves to an untracked `CLAUDE.local.md`.

The history is kept, not restarted. At release, `git filter-repo` removes those paths from every commit, which drops the commits that touched nothing else. Every commit message is reworded to make its point without citing an ADR, a ticket or the glossary. Past file contents are left as they were. A stale citation in an old commit's comment is a historical record. The GitHub repository is then deleted and recreated, and the filtered history is pushed, because after a force-push GitHub still serves the old commits by SHA. Until then the repository stays public as it is, since only the recreation removes what was pushed.

The repository and the PyPI distribution are both `naiad-cli`, and the command is `naiad`. `naiad` on PyPI belongs to an empty 2016 project. No PEP 541 transfer is filed, because a later move would make every adopter reinstall under a new name to gain nothing they type.

## Considered alternatives

**Publishing the record** is the usual open-source practice, and it would let contributors follow the ADRs. It was rejected because the record is the maintainer's working surface, written for the maintainer's agents.

**A fresh single-commit history** is simpler and needs no message rewrites. It was rejected because the history of the code is worth keeping.

**A private companion repository for the record** would give it a remote. **A private source repository with the public one as a filtered export** would keep the record tracked. Both were rejected. The first adds a second remote to maintain for a backup the maintainer does not want. The second splits the code across two repositories and makes every outside pull request a hand port.

## Consequences

A new clone has no record until the maintainer sets up the excludes again. Contributions are accepted, and so contributors are held only to what the public repository states: a `CONTRIBUTING.md` asks for an issue before a non-trivial pull request and for tests first, and takes contributions under the outbound licenses (MIT and 0BSD) with no CLA. The copyright line stays `Janriz Libres`.
