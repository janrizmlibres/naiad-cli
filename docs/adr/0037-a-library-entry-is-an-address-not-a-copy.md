# A library entry is an address, not a copy

> Amended by ADR 0049.

A Run parked at `handover` on a `wontfix` ticket, which ADR 0027 had closed six days earlier. The Prompt it obeyed was right for the file it read and four days behind the file under review: the library held `matt-pocock.toml` as a copy taken on 31 July, three ADRs old. Beside it sat a symlink the operator had made one minute later, pointing at the repository's `workflows/` directory — an attempt to make the library follow the repository that resolved nothing, because a name opens `library/<name>.toml` and never a subdirectory. The copy answered the name, so every Run started, and nothing anywhere reported the split. The operator held a correct model of how the library should behave while the disk disagreed with it for four days.

We decided the library is an index rather than a store. A library entry is an address, and the Workflow file it names lives where its author maintains it — in a repository, under review, with its ADRs beside it. A symlink is what an entry is made of. This revises the shape ADR 0023 described rather than the resolution it decided: the entrance still resolves a name to a path, and the shape of the argument still decides name from path.

`naiad install` makes the link for the Workflow that ships, beside the hooks and the adopt skill. The three now stand together for one reason: each is something an operator sets up once and re-runs without thinking, and each self-heals what an earlier run left behind. An arrangement made by hand is the act that just failed, and a convention written into a document defends nobody against it — reading the document requires already suspecting the library, which is what nobody does.

The rule on what install finds follows `install_adopt_skill`. Nothing there: the link is made. A symlink: it is replaced, because an address is cheap to rewrite and a wrong one is what this ADR exists to prevent. A regular file: **refused**, because deleting a file a human put there to install one they can reinstall at any time trades their work for ours — and because the refusal is the report that was missing. Run against the library as it stood on 3 August, install would have named the stale copy out loud.

The link points into the source checkout, `workflows/` beside the package, which is where the file actually is: `pyproject.toml` packages `naiad*` alone, so a distribution carries no Workflow at all. An edit therefore reaches even a running Run, because a Run loads its Workflow on every tick rather than once at kickoff (ADR 0023 — a name buys no snapshot). Where no such directory stands beside the package, install refuses the link in one sentence and carries on; passing quietly is the failure mode this whole decision is about.

Only the shipped Workflow is install's to link. A Workflow maintained in another repository is linked by hand, and this closes nothing for a copy someone drops in the library by choice.

## Considered alternatives

**Documenting the convention.** Rejected above: the operator already believed the convention was in force.

**Packaging the Workflow** into `naiad/workflows/` so a distribution carries it. Rejected because it reintroduces the fault one step along — the library would then address a copy the package manager made, refreshed on reinstall rather than never. Better than four days stale, still not the file under review.

**Recording the Workflow's content on the Run**, as a hash beside the path, so that which file ran becomes answerable later. Rejected because an address cannot go stale and only a copy can, so the field would be a permanent cost against a fault this decision removes — and a hash names no commit, so the diagnosis is still a search of git history. The Run log already carries the tell: a `delivered` line names the candidate States, and the drift showed there at the first delivery as a missing `triage`.

## Consequences

Naiad now writes the library, where ADR 0023 said it only reads. That sentence of 0023 is revised here, and the home's own docstring with it. What a human writes there is still theirs — install refuses a regular file rather than replacing it, which is the boundary that keeps "Naiad writes the library" from meaning "Naiad owns it".

Install now behaves differently depending on how Naiad was obtained, and says which case it is in. That is the price of addressing the file under review rather than a copy of it.
