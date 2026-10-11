# The license

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

Which license does Naiad ship under? The owner's decision alone. MIT is shortest; Apache-2.0 adds an explicit patent grant and a NOTICE convention; a copyleft license changes what adopters may do with their own workflows. Decide the license, the copyright holder line, and whether the shipped workflow files carry the same license or a more permissive one, since they are configuration an adopter copies.

## Answer

- **The code is MIT.** Apache-2.0's patent grant and NOTICE convention buy little for a small CLI with one author. Copyleft would leave adopters unsure whether their own Workflows are derivative works.
- **Holder line:** `Copyright (c) 2026 Janriz Libres`. The year is the first year of publication and is never turned into a range. A "contributors" line waits for a contribution policy, which belongs to "The public repository".
- **The two Workflow files are 0BSD**: `naiad/workflows/starter.toml` and `workflows/matt-pocock.toml`. A copied starter owes no attribution, so the adopter owns the copy outright.
- **Where it is declared:** `LICENSE` holds the MIT text and names the two 0BSD files. `LICENSES/0BSD.txt` holds the 0BSD text. `pyproject.toml` gets `license = "MIT AND 0BSD"` with both files in `license-files` (this needs `setuptools>=77`, per "Publishing to PyPI"). The README's license section names both in one line. No `SPDX-License-Identifier` header goes in the TOML files.
- Recorded in ADR 0056 (`docs/adr/0056-the-workflow-files-are-0bsd-and-the-rest-is-mit.md`).
