# Where shipped and authored workflows live

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

After `uv tool install naiad`, where is the shipped starter, and how does the library hold it beside authored workflows? Today ADR 0037 links the library to `workflows/` beside the package in a source checkout, `pyproject.toml` packages `naiad*` alone, and install refuses the link where that directory is absent, which is exactly the case a PyPI install is in. Decide: whether the starter is packaged (ADR 0037 rejected packaging for the personal file because the library would address a copy; a starter an adopter is expected to copy and change may be different); whether an adopter's first act is `naiad workflow new --from starter` (a copy they own) rather than running the shipped file by name; what the library holds as regular files versus symlinks, and what the revised ADR 0037 says; whether `naiad install` still makes a link at all. Record the revision as an ADR amending 0037.

## Answer

Resolved 2026-09-19 by a grilling round. Recorded as ADR 0049, `docs/adr/0049-the-library-is-a-store-and-the-starter-is-copied-on-request.md`, which amends 0037; the glossary's Workflow library entry is revised to match. One standing decision in the map's Notes is reversed by this answer: shipped workflows do not stay symlinks.

### The decision

1. **The starter is package data.** It moves into the package at `naiad/workflows/starter.toml` and ships in the wheel, read through `importlib.resources`. The root `workflows/` directory stops being where shipped files live; where the personal file goes is ticket 05's. ADR 0037's rejection of packaging is reversed for the shipped file: that rejection was about the library addressing a copy, and the library no longer addresses the starter at all.
2. **The library is a store.** `~/.naiad/workflows/` holds regular files an adopter owns. Every entry is theirs, including the starter once it lands there. A symlink is still a valid entry, made by hand for a Workflow maintained in a repository (0037's own rule for "another repository"), and the writing verbs write through it: a hand-made link is the adopter's and so is the file behind it. No verb refuses an entry for being a link.
3. **`naiad install` copies the starter on request, never by default.** `naiad install --starter` writes `starter.toml` into the library as a regular file. A bare `naiad install` touches the library not at all; install stays non-interactive. There is no `--no-starter`.
4. **Re-running `--starter`.** No file: written. A file byte-identical to the shipped starter: rewritten, so an older copy is refreshed and nothing is lost. A file that differs: **refused** in one sentence, "starter.toml differs from the shipped starter; pass --force or move it aside", because the difference is the adopter's work and 0037's refusal exists so a re-run done without thinking never destroys it. `--force` overwrites. A symlink named `starter.toml` is treated as a file that differs: refused, never replaced.
5. **The starter runs by name straight after `naiad install --starter`**: `naiad queue add starter "..."`. The adopter's first act is running the shipped file, not copying it. `naiad workflow new <name> --from starter` still exists for a second copy; `--from` takes a name or a path by shape, and the copy's `name` key is rewritten to the new stem so it is never misfiled.
6. **Rename exists.** An adopter may rename any library workflow: the file and its `name` key move together, and the verb refuses while a queued Entry or live Run addresses the file (Entries store resolved paths). Its exact shape belongs to ticket 03, which already lists rename among the candidates; a comment there records this.
7. **`naiad workflow list`** distinguishes nothing about origin. There is no shipped kind in the library any more, only the adopter's files. A dangling hand-made link is named as broken by both the listing and the resolver rather than reported as a missing name.
8. **The maintainer's own library** holds a hand-made link to the checkout's `naiad/workflows/starter.toml`, or runs it by path. `naiad install --starter` on a machine with an editable install would copy the checkout file and let it go stale, which is the fault 0037 records; the hand link is 0037's remedy and it stays.
9. **What goes from the code.** `SHIPPED_WORKFLOWS` pointing two levels above the package, `link_shipped_workflows`, `_refuse_a_copy` and its "a copy can fall behind" wording, and install's "no workflows directory beside this naiad" branch. `shipped_workflows()` reads the package's resources instead. Tests of the shipped file point into the package.

### Considered and rejected

- **Install links the packaged file** (0037 as it stands, retargeted into site-packages). Rejected: the adopter would own nothing until they copied, and the verbs would have to refuse the one workflow a new install holds. The user wants the starter to be theirs from the first minute.
- **Name resolution falling back to the packaged set** when the library misses. Rejected: two sources for one name, against ADR 0023's one-place resolution.
- **Starter written by default, opted out with `--no-starter`.** Rejected: the adopter chooses to have it; an install should leave the library untouched unless asked.
- **An interactive `y/n` in install.** Rejected: install is re-run without thinking and from scripts; a flag is the whole of the choice.
- **Overwriting an edited starter on re-run**, the user's first proposal. Rejected in favour of the refusal plus `--force`: the request is honoured and no edit is lost to a re-run.
