"""The POSIX installer falls back to uv's GitHub release installer.

The primary astral.sh endpoint can fail independently of GitHub (for example
through a transient proxy/Cloudflare connection reset).  The installer must
try the official GitHub release copy before treating uv bootstrap as failed.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def _exe(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@pytest.mark.linux_only
def test_uv_bootstrap_uses_github_release_when_astral_download_resets(tmp_path: Path) -> None:
    """Drive the prerequisite stage with a reset primary download and working mirror."""
    home = tmp_path / "home"
    hermes_home = home / ".hermes"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl_log = tmp_path / "curl-urls.log"

    _exe(bin_dir / "python3.13", "#!/bin/sh\n[ \"$1\" = --version ] && echo 'Python 3.13.12'\nexit 0\n")
    _exe(
        bin_dir / "curl",
        "#!/bin/sh\n"
        "[ \"$1\" = --version ] && { echo 'curl 8.0'; exit 0; }\n"
        "url=\"\"; out=\"\"\n"
        "while [ $# -gt 0 ]; do\n"
        "  case \"$1\" in -o) out=$2; shift 2;; http*) url=$1; shift;; *) shift;; esac\n"
        "done\n"
        "printf '%s\\n' \"$url\" >> \"$CURL_URL_LOG\"\n"
        "if [ \"$url\" = https://astral.sh/uv/install.sh ]; then\n"
        "  echo 'curl: (35) Recv failure: Connection reset by peer' >&2; exit 35\n"
        "fi\n"
        "cat > \"$out\" <<'EOF'\n"
        "#!/bin/sh\n"
        "mkdir -p \"$UV_UNMANAGED_INSTALL\"\n"
        "cat > \"$UV_UNMANAGED_INSTALL/uv\" <<'UVEOF'\n"
        "#!/bin/sh\n"
        "[ \"$1\" = --version ] && { echo 'uv 0.9.99'; exit 0; }\n"
        "if [ \"$1\" = python ] && [ \"$2\" = find ]; then\n"
        "  [ \"$3\" = 3.11 ] && exit 2\n"
        "  [ \"$3\" = --system ] && [ \"$4\" = '>=3.11,<3.14' ] && { echo \"$UV_TEST_PYTHON\"; exit 0; }\n"
        "fi\n"
        "exit 0\n"
        "UVEOF\n"
        "chmod +x \"$UV_UNMANAGED_INSTALL/uv\"\n"
        "EOF\n",
    )
    for tool in ("git", "node", "npm", "rg", "g++", "c++"):
        _exe(bin_dir / tool, "#!/bin/sh\ncase \"$1\" in --version|-v) echo 'v26.0.0 2.50.0';; esac\nexit 0\n")

    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "HERMES_HOME": str(hermes_home),
        "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', os.defpath)}",
        "CURL_URL_LOG": str(curl_log),
        "UV_TEST_PYTHON": str(bin_dir / "python3.13"),
        "TMPDIR": str(tmp_path),
    })
    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--stage", "prerequisites", "--non-interactive"],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    urls = curl_log.read_text(encoding="utf-8").splitlines()
    assert urls[:2] == [
        "https://astral.sh/uv/install.sh",
        "https://github.com/astral-sh/uv/releases/latest/download/uv-installer.sh",
    ], (urls, result.stdout)
    assert "Managed uv installed (uv 0.9.99)" in result.stdout
    assert (hermes_home / "bin" / "uv").is_file()