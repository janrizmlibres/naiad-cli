# The library is a store, and the starter is copied on request

ADR 0037 made the library an index: an entry is a symlink, the file lives where its author maintains it, and `naiad install` makes the link for the Workflow that ships, into `workflows/` beside the package in a source checkout. That held while every operator was the maintainer. An adopter installing from PyPI has no checkout, `pyproject.toml` packages `naiad*` alone, and install's answer to them was one sentence saying the library gained nothing. The first open-source release needs a starter Workflow that runs the minute Naiad is installed, and an adopter who then edits it as their own.

We decided the library is a store. `~/.naiad/workflows/` holds regular files the adopter owns, written by them or by the authoring verbs, and every entry in it is theirs. The starter ships inside the package, at `naiad/workflows/starter.toml`, and `naiad install --starter` copies it into the library as a regular file; a bare `naiad install` leaves the library alone. The adopter runs it by name at once and edits it in place, because it is theirs from the first minute rather than after a copying step the verbs would otherwise force on them. This reverses 0037's rejection of packaging for the shipped file: that rejection was about the library addressing a copy, and the library now addresses the starter through nothing.

0037's refusal survives with its reason and a new subject. Re-running `--starter` over a file byte-identical to the shipped starter rewrites it, so an older copy is refreshed and nothing is lost. Over a file that differs it refuses in one sentence and names `--force`, because the difference is the adopter's work and a re-run done without thinking must not destroy it. A symlink of that name is refused the same way and never replaced.

A symlink remains a valid entry, made by hand, for a Workflow maintained in a repository under review: this is 0037's own rule for a file in another repository, and it is how the maintainer's library reaches the checkout's starter without a copy going stale. The verbs write through such a link, since the link and the file behind it are both the adopter's. A link that points at nothing is named as broken by the listing and the resolver rather than reported as a missing name.

## Considered alternatives

**Install links the packaged file**, 0037 retargeted into the tool venv, where an upgrade rebuilds the venv in place so the link follows the shipped starter. Rejected because the adopter would then own nothing until they copied, and the verbs would have to refuse the one Workflow a fresh install holds.

**Name resolution falling back to the package** when the library misses. Rejected: two places for one name, against ADR 0023's resolution in one place.

**Starter written by default with a `--no-starter` opt-out**, or an interactive prompt in install. Rejected: install is re-run without thinking and from scripts, and an install should not touch the library unless asked. The flag is the whole of the choice.

**Overwriting an edited starter on re-run.** Rejected in favour of the refusal plus `--force`: the request is honoured and no edit is lost.

## Consequences

The map's earlier position that shipped Workflows stay symlinks is reversed; Naiad makes no symlink any more. `SHIPPED_WORKFLOWS`, `link_shipped_workflows`, the refusal of a copy and install's "no workflows directory" branch go; the shipped file is read as a package resource, and its tests point into the package. The root `workflows/` directory is no longer where a shipped file lives.

A `naiad workflow rename` verb exists, moving the file and its `name` key together so a renamed file is never misfiled, and refusing while a queued Entry or live Run addresses the file, since an Entry stores the resolved path (ADR 0023).

The maintainer's own library must hold a hand-made link to the checkout; `naiad install --starter` there would copy the checkout file and let it go stale, which is exactly what 0037 was written after.
