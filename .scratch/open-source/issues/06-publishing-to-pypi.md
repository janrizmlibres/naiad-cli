# Publishing to PyPI

Type: research
Mode: AFK
Status: resolved
Blocked by:

## Question

Is the name `naiad` available on PyPI, and what is the minimal setup to publish this setuptools package from GitHub Actions with trusted publishing, as of September 2026? Surface: whether `naiad` (and fallbacks such as `naiad-cli`, `naiad-workflow`) is taken; the current trusted-publishing flow (PyPI pending publisher, the `pypa/gh-action-pypi-publish` action, `uv build` and `uv publish` as alternatives); what `pyproject.toml` still lacks for a release (readme, license, classifiers, urls, dynamic version or not); and whether `uv tool install naiad` needs anything beyond a published wheel.

Context: findings land on branch `research/pypi-publishing` as `docs/research/pypi-publishing.md`, written by a research subagent fired at charting (2026-09-18).

## Answer

Resolved 2026-09-18 by a research subagent. Full findings with sources: `docs/research/pypi-publishing.md` on branch `research/pypi-publishing` (commit 24ce6e1).

- **`naiad` is taken on PyPI.** A 2016 project by another author, one release with zero distribution files, its GitHub repository archived in 2024. It can only be obtained through a PEP 541 name-transfer request on pypi/support; the case is strong (empty project, abandoned) but there is no timeline. `naiad-cli`, `naiad-workflow` and `naiads` are free per the JSON API; whether PyPI's confusable-name check rejects them as too close to `naiad` could not be verified.
- **Trusted publishing:** register a PyPI pending publisher (project name, owner/repo, workflow filename, environment `pypi`) before the project exists; a GitHub environment `pypi` with a required reviewer; a separate publish job with `permissions: id-token: write` using `pypa/gh-action-pypi-publish@release/v1`. A pending publisher for `naiad` cannot be created while the existing record stands, so the name decision precedes the setup.
- **uv works as the client:** `uv build` builds with the existing setuptools backend; `uv publish` with `trusted-publishing = automatic` needs no credentials.
- **`pyproject.toml` builds today** (verified) but the wheel carries no readme, license, author, classifiers or URLs. To add: README.md, LICENSE, `setuptools>=77` for SPDX `license`, plus `readme`, `license`, `license-files`, `authors`, `classifiers`, `[project.urls]`. Static version is fine. No `.github/workflows/` exists yet.
- **`uv tool install` needs only a published wheel** (verified against the built wheel). Published as `naiad-cli` it still yields the `naiad` command; only `uvx` would need `--from`.

Consequence for the map: the PyPI name is now a decision, folded into **The public repository** (08), which already asks whether the PyPI and repository names must match.
