"""Regression: install/update E2E must never test an unsupported downgrade."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PICKER = REPO_ROOT / "scripts" / "sandbox" / "pick-release-tags.sh"


def run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True)


def commit(repo: Path, message: str, content: str) -> None:
    (repo / "state.txt").write_text(content)
    run("git", "add", "state.txt", cwd=repo)
    run("git", "commit", "-m", message, cwd=repo)


def test_picker_excludes_release_tags_not_ancestral_to_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run("git", "init", "-q", cwd=repo)
    run("git", "config", "user.email", "test@example.invalid", cwd=repo)
    run("git", "config", "user.name", "Test", cwd=repo)

    commit(repo, "release base", "base\n")
    run("git", "tag", "v2026.9.14", cwd=repo)
    base = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=repo, text=True).strip()

    commit(repo, "fork head", "fork\n")
    fork_head = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=repo, text=True).strip()

    run("git", "checkout", "-q", "-b", "release", base, cwd=repo)
    commit(repo, "new upstream release", "release\n")
    run("git", "tag", "v2026.9.21", cwd=repo)
    run("git", "checkout", "-q", fork_head, cwd=repo)

    result = subprocess.run(
        ("bash", str(PICKER), "--count", "2", "--repo", str(repo)),
        check=True,
        text=True,
        capture_output=True,
    )

    assert json.loads(result.stdout) == ["v2026.9.14"]
