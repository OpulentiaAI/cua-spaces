"""Behavior of the release pipeline guard on repositories with and without issues.

The guard step is read out of the workflow and executed against a stub `gh`, so
the test covers the real step body: a repository with issues disabled must still
pass on a healthy pipeline and still fail on a stuck one.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/release-pipeline-guard.yml"
STEP_NAME = "Check release pipeline state"

STUB = """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$GH_STUB_LOG"
case "$*" in
  "api repos/"*" --jq .has_issues") printf '%s\\n' "$GH_STUB_HAS_ISSUES" ;;
  "api --paginate repos/"*"/issues?"*) printf '%s' "${GH_STUB_PENDING:-}" ;;
  "api --paginate repos/"*"/releases?"*) printf '%s' "${GH_STUB_DRAFTS:-}" ;;
  "issue list"*) printf '%s' "${GH_STUB_EXISTING:-}" ;;
  *) : ;;
esac
"""

# Merged 30 days before the test runs, so the 30-minute threshold trips without
# depending on a fixed date.
OLD_MERGE = "2020-01-01T00:00:00Z"
PENDING_ROW = f"42\t{OLD_MERGE}\trelease: cua-spaces 1.2.3\n"


def guard_script() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    steps = workflow["jobs"]["guard"]["steps"]
    step = next(s for s in steps if s.get("name") == STEP_NAME)
    return step["run"]


def run_guard(tmp_path: Path, **stub_env: str) -> tuple[subprocess.CompletedProcess, str]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(STUB)
    gh.chmod(0o755)
    log = tmp_path / "gh.log"
    log.write_text("")
    summary = tmp_path / "summary.md"
    summary.write_text("")
    script = tmp_path / "step.sh"
    script.write_text(guard_script())

    env = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "GH_TOKEN": "stub",
        "REPO": "OpulentiaAI/cua-spaces",
        "GITHUB_STEP_SUMMARY": str(summary),
        "GH_STUB_LOG": str(log),
        "GH_STUB_HAS_ISSUES": "false",
        **stub_env,
    }
    result = subprocess.run(
        ["bash", str(script)], env=env, capture_output=True, text=True, check=False
    )
    return result, log.read_text() + "\n---summary---\n" + summary.read_text()


def test_the_step_body_is_valid_bash(tmp_path: Path) -> None:
    script = tmp_path / "step.sh"
    script.write_text(guard_script())
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_healthy_pipeline_passes_when_issues_are_disabled(tmp_path: Path) -> None:
    result, seen = run_guard(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Release pipeline healthy." in result.stdout
    # A disabled issue tracker is never called.
    assert "issue list" not in seen
    assert "issue create" not in seen


def test_stuck_pipeline_fails_and_reports_in_the_summary_when_issues_are_disabled(
    tmp_path: Path,
) -> None:
    result, seen = run_guard(tmp_path, GH_STUB_PENDING=PENDING_ROW)
    assert result.returncode == 1, result.stderr
    assert "::error::Release pipeline is stuck" in result.stdout
    assert "Merged PR #42" in result.stdout
    # The report lands in the run summary instead of a tracking issue.
    assert "Merged PR #42" in seen.split("---summary---", 1)[1]
    assert "issue create" not in seen
    assert "issue list" not in seen


def test_stuck_pipeline_opens_the_tracking_issue_when_issues_are_enabled(
    tmp_path: Path,
) -> None:
    result, seen = run_guard(
        tmp_path, GH_STUB_HAS_ISSUES="true", GH_STUB_PENDING=PENDING_ROW
    )
    assert result.returncode == 1, result.stderr
    assert "issue list" in seen
    assert "issue create" in seen


def test_stuck_pipeline_edits_the_existing_tracking_issue(tmp_path: Path) -> None:
    result, seen = run_guard(
        tmp_path,
        GH_STUB_HAS_ISSUES="true",
        GH_STUB_PENDING=PENDING_ROW,
        GH_STUB_EXISTING="7",
    )
    assert result.returncode == 1, result.stderr
    assert "issue edit 7" in seen
    assert "issue create" not in seen


def test_recovered_pipeline_closes_the_tracking_issue(tmp_path: Path) -> None:
    result, seen = run_guard(
        tmp_path, GH_STUB_HAS_ISSUES="true", GH_STUB_EXISTING="7"
    )
    assert result.returncode == 0, result.stderr
    assert "issue close 7" in seen
