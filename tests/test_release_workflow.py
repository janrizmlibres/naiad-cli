"""The workflow that publishes a tag to PyPI: it runs on a version tag only, and
the one job that may mint a publishing token is the one that uploads, in the
`pypi` environment, after the build job has tested and built the distributions.
"""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())


def _steps(job: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = WORKFLOW["jobs"][job]["steps"]
    return steps


def _runs(job: str) -> str:
    return "\n".join(step.get("run", "") for step in _steps(job))


def test_it_runs_only_on_a_version_tag() -> None:
    # YAML 1.1 reads the bare key `on` as the boolean True.
    triggers = WORKFLOW[True]
    assert list(triggers) == ["push"]
    assert list(triggers["push"]) == ["tags"]
    assert all(pattern.startswith("v") for pattern in triggers["push"]["tags"])


def test_the_publish_job_needs_the_build_job() -> None:
    assert WORKFLOW["jobs"]["publish"]["needs"] == "build"


def test_only_the_publish_job_holds_id_token_write() -> None:
    assert "id-token" not in WORKFLOW.get("permissions", {})
    assert "id-token" not in WORKFLOW["jobs"]["build"].get("permissions", {})
    assert WORKFLOW["jobs"]["publish"]["permissions"]["id-token"] == "write"


def test_the_publish_job_runs_in_the_pypi_environment() -> None:
    environment = WORKFLOW["jobs"]["publish"]["environment"]
    name = environment["name"] if isinstance(environment, dict) else environment
    assert name == "pypi"


def test_the_build_job_tests_type_checks_and_builds() -> None:
    runs = _runs("build")
    assert "pytest" in runs
    assert "mypy" in runs
    assert "uv build" in runs


def test_the_build_job_refuses_a_tag_that_is_not_the_project_version() -> None:
    assert "GITHUB_REF_NAME" in _runs("build")


def test_the_build_job_uploads_dist_for_the_publish_job_to_download() -> None:
    uploaded = [s for s in _steps("build") if s.get("uses", "").startswith("actions/upload-artifact")]
    downloaded = [s for s in _steps("publish") if s.get("uses", "").startswith("actions/download-artifact")]
    assert len(uploaded) == len(downloaded) == 1
    assert uploaded[0]["with"]["path"] == "dist/"
    assert downloaded[0]["with"]["name"] == uploaded[0]["with"]["name"]
    assert downloaded[0]["with"]["path"] == "dist/"


def test_the_publish_job_uploads_with_the_pypi_action_and_no_token() -> None:
    publishes = [s for s in _steps("publish") if s.get("uses", "").startswith("pypa/gh-action-pypi-publish@")]
    assert len(publishes) == 1
    assert "password" not in publishes[0].get("with", {})
    assert "secrets." not in (ROOT / ".github/workflows/release.yml").read_text()
