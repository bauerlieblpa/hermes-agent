"""The release-tag picker reads origin, not the local checkout, and keeps CalVer order."""
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sandbox" / "pick-release-tags.sh"


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _pick(repo, *args):
    return subprocess.run(["bash", str(SCRIPT), *args, "--repo", str(repo)], check=True, capture_output=True, text=True).stdout.strip()


def _origin_with_tags(root, tags):
    origin = root / "origin.git"
    _git(root, "init", "--bare", "-b", "main", str(origin))
    seed = root / "seed"
    _git(root, "init", "-b", "main", str(seed))
    _git(seed, "config", "user.name", "fixture")
    _git(seed, "config", "user.email", "fixture@example.invalid")
    for tag in tags:
        _git(seed, "commit", "--allow-empty", "-m", tag)
        _git(seed, "tag", tag)
    _git(seed, "push", str(origin), "main", "refs/tags/*:refs/tags/*")
    return origin


def test_picking_reads_origin_not_local_tags(tmp_path):
    # CalVer names where version order is the chronology but lexicographic
    # order is not: v2026.4.13 sorts before v2026.4.3 as plain text.
    origin = _origin_with_tags(tmp_path, ["v2026.4.3", "v2026.4.13", "v2026.9.15"])
    # --no-tags leaves local tag refs absent; commits reachable from main
    # can still be present, including lightweight tags' target objects.
    _git(tmp_path, "clone", "--no-local", str(origin), str(tmp_path / "with-tags"))
    _git(tmp_path, "clone", "--no-local", "--no-tags", str(origin), str(tmp_path / "tagless"))
    assert _pick(tmp_path / "tagless", "--count", "2") == '["v2026.4.3","v2026.9.15"]'
    # Only the picked tag refs are materialized; ancestry may fetch other objects.
    assert _git(tmp_path / "tagless", "tag", "--list").stdout.split() == ["v2026.4.3", "v2026.9.15"]
    expected = '["v2026.4.3","v2026.4.13","v2026.9.15"]'
    assert _pick(tmp_path / "tagless", "--count", "5") == expected
    assert _pick(tmp_path / "with-tags", "--count", "5") == expected


def test_picking_rejects_schemes_other_than_calver(tmp_path):
    origin = _origin_with_tags(tmp_path, ["v0.27.0"])
    _git(tmp_path, "clone", "--no-local", "--no-tags", str(origin), str(tmp_path / "tagless"))
    result = subprocess.run(["bash", str(SCRIPT), "--repo", str(tmp_path / "tagless")], check=False, capture_output=True, text=True)
    assert result.returncode != 0
    assert "release tags found on origin" in result.stderr



def test_picker_excludes_release_tags_not_ancestral_to_head(tmp_path):
    origin = _origin_with_tags(tmp_path, ["v2026.9.14"])
    seed = tmp_path / "seed"
    _git(seed, "checkout", "-b", "release")
    _git(seed, "commit", "--allow-empty", "-m", "unmerged release")
    _git(seed, "tag", "-a", "v2026.9.21", "-m", "annotated unmerged")
    _git(seed, "push", str(origin), "release", "refs/tags/v2026.9.21")
    checkout = tmp_path / "fork"
    _git(tmp_path, "clone", "--no-local", "--no-tags", str(origin), str(checkout))
    _git(checkout, "config", "user.name", "fixture")
    _git(checkout, "config", "user.email", "fixture@example.invalid")
    _git(checkout, "commit", "--allow-empty", "-m", "fork-only change")
    assert _pick(checkout, "--count", "2") == '["v2026.9.14"]'
    assert _git(checkout, "tag", "--list").stdout.split() == ["v2026.9.14"]


def test_picker_accepts_annotated_ancestor_tag(tmp_path):
    origin = _origin_with_tags(tmp_path, ["v2026.4.3"])
    seed = tmp_path / "seed"
    _git(seed, "commit", "--allow-empty", "-m", "next release")
    _git(seed, "tag", "-a", "v2026.4.13", "-m", "annotated ancestor")
    _git(seed, "push", str(origin), "main", "refs/tags/v2026.4.13")
    checkout = tmp_path / "tagless"
    _git(tmp_path, "clone", "--no-local", "--no-tags", str(origin), str(checkout))
    assert _pick(checkout) == '["v2026.4.3","v2026.4.13"]'
    assert _git(checkout, "cat-file", "-t", "refs/tags/v2026.4.13").stdout.strip() == "tag"


def test_picker_fails_when_no_release_is_ancestral(tmp_path):
    origin = _origin_with_tags(tmp_path, ["v2026.4.3"])
    checkout = tmp_path / "unrelated"
    _git(tmp_path, "init", "-b", "main", str(checkout))
    _git(checkout, "config", "user.name", "fixture")
    _git(checkout, "config", "user.email", "fixture@example.invalid")
    _git(checkout, "commit", "--allow-empty", "-m", "unrelated history")
    _git(checkout, "remote", "add", "origin", str(origin))
    result = subprocess.run(["bash", str(SCRIPT), "--repo", str(checkout)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "no release tags ancestral to HEAD" in result.stderr
    assert _git(checkout, "tag", "--list").stdout == ""


def test_picker_rejects_shallow_history(tmp_path):
    origin = _origin_with_tags(tmp_path, ["v2026.4.3", "v2026.4.13"])
    checkout = tmp_path / "shallow"
    _git(tmp_path, "clone", "--no-local", "--no-tags", "--depth", "1", str(origin), str(checkout))
    result = subprocess.run(["bash", str(SCRIPT), "--repo", str(checkout)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "shallow history" in result.stderr
    assert _git(checkout, "tag", "--list").stdout == ""


def test_picker_refuses_divergent_local_selected_tag(tmp_path):
    origin = _origin_with_tags(tmp_path, ["v2026.4.3", "v2026.4.13"])
    checkout = tmp_path / "tagless"
    _git(tmp_path, "clone", "--no-local", "--no-tags", str(origin), str(checkout))
    _git(checkout, "tag", "v2026.4.13", "HEAD~1")
    before = _git(checkout, "rev-parse", "refs/tags/v2026.4.13").stdout
    result = subprocess.run(["bash", str(SCRIPT), "--count", "1", "--repo", str(checkout)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "local tag differs" in result.stderr
    assert _git(checkout, "rev-parse", "refs/tags/v2026.4.13").stdout == before


def test_picker_uses_explicit_release_remote_when_fork_origin_has_no_tags(tmp_path):
    releases = _origin_with_tags(tmp_path, ["v2026.4.3", "v2026.4.13"])
    fork = tmp_path / "fork.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(fork))
    _git(tmp_path / "seed", "push", str(fork), "main")
    checkout = tmp_path / "checkout"
    _git(tmp_path, "clone", "--no-local", "--no-tags", str(fork), str(checkout))
    assert _git(checkout, "ls-remote", "--tags", "origin").stdout == ""
    assert _pick(checkout, "--remote", str(releases), "--count", "2") == '["v2026.4.3","v2026.4.13"]'
    assert _git(checkout, "tag", "--list").stdout.split() == ["v2026.4.13", "v2026.4.3"]
