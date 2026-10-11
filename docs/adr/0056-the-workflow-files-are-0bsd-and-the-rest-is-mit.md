# The Workflow files are 0BSD, and the rest of Naiad is MIT

Naiad ships under the MIT license, `Copyright (c) 2026 Janriz Libres`. MIT asks that its notice travel with "all copies or substantial portions" of the software. `naiad install --starter` copies the starter into the adopter's library as a regular file the adopter edits and owns (ADR 0049). Read strictly, every copied starter would then owe the MIT text. A Workflow file has no place for it, because its comments carry no explanation.

We decided the two Workflow files, `naiad/workflows/starter.toml` and `workflows/matt-pocock.toml`, are licensed 0BSD. 0BSD has no attribution condition, so an adopter's copy owes nothing to Naiad and carries no header. Everything else in the repository is MIT. `LICENSE` holds the MIT text and names the two files it does not cover, `LICENSES/0BSD.txt` holds the 0BSD text, `pyproject.toml` declares `license = "MIT AND 0BSD"` with both files in `license-files`, and the README names both licenses in one line.

## Considered alternatives

**Apache-2.0**, alone or dual with MIT, adds a patent grant and a NOTICE convention. That protection does little for a small CLI with one author that drives another tool, and it costs every redistributor the NOTICE bookkeeping. **A copyleft license** leaves it unclear whether an adopter's own Workflow is a derivative work, and that doubt alone deters adopters.

**MIT for the Workflow files too** keeps one license, but every copied starter would owe attribution. **CC0** has the same effect as 0BSD, but some companies reject it for software. **An `SPDX-License-Identifier` line at the top of each Workflow file** would be copied into every adopter's library as a comment that explains nothing about the Workflow.

## Consequences

A new file under `naiad/workflows/` or `workflows/` is 0BSD only once `LICENSE` names it. Until then it falls under MIT.
