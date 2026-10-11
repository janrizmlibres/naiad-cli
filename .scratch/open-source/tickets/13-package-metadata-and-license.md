# 13 — Package metadata and license

Status: resolved
Mode: AFK
Blocked by: 04
Spec: [PRD](../PRD.md), "Packaging, naming and license"; ADR 0056; research on branch `research/pypi-publishing`

**What to build:** A wheel that can go to PyPI.

- The distribution is named `naiad-cli`, at version `0.1.0`, with the `naiad` command unchanged.
- The build requires `setuptools>=77`.
- The metadata gains `readme`, `license = "MIT AND 0BSD"`, `license-files` (both texts), `authors`, `classifiers` and `[project.urls]`.
- `LICENSE` holds the MIT text, `Copyright (c) 2026 Janriz Libres`, and names the two 0BSD Workflow files. `LICENSES/0BSD.txt` holds the 0BSD text.
- No SPDX header goes in either TOML file.

- [ ] `uv build` produces a wheel whose metadata carries the license expression, both license files, the readme and the URLs.
- [ ] `uv tool install` of that wheel into a clean tool environment yields a `naiad` whose `naiad install --starter` writes the packaged starter.
- [ ] `LICENSE` names both 0BSD files.
