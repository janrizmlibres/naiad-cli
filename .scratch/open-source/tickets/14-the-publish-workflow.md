# 14 — The publish workflow

Status: resolved
Mode: AFK
Blocked by: 13
Spec: [PRD](../PRD.md), "Packaging, naming and license"; research on branch `research/pypi-publishing`

**What to build:** A GitHub Actions workflow triggered by a version tag, with two jobs.

1. **Build:** runs the test suite (workers capped) and mypy, then `uv build`, then uploads `dist/` as an artifact.
2. **Publish:** downloads the artifact and publishes with `pypa/gh-action-pypi-publish`. It has `permissions: id-token: write`, runs in the `pypi` environment, and holds no token.

Registering the pending publisher and creating the environment are ticket 22's (HITL).

- [ ] The workflow runs only on a version tag, and the publish job needs the build job.
- [ ] Only the publish job holds `id-token: write`, and it names the `pypi` environment.
- [ ] The workflow file passes a YAML lint or `actionlint`, whichever is available.
