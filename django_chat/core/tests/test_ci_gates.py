import subprocess
from pathlib import Path

import pytest
import yaml
from scripts.check_docs import check_docs

ROOT = Path(__file__).resolve().parents[3]


def test_browser_ci_enables_and_runs_existing_suite() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    browser = workflow["jobs"]["browser"]
    assert browser["env"]["DJANGO_CHAT_BROWSER_TESTS"] == "1"
    commands = "\n".join(step.get("run", "") for step in browser["steps"])
    assert "uv sync --locked" in commands
    assert "playwright install --with-deps chromium" in commands
    assert "pytest django_chat/core/tests/test_browser_js.py" in commands


def test_docs_check_builds_and_rejects_missing_page(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    page = tmp_path / "docs/index.md"
    page.write_text("# Synthetic documentation\n")
    config = tmp_path / "zensical.toml"
    config.write_text('[project]\nsite_name = "Synthetic"\nnav = [{"Home" = "index.md"}]\n')
    check_docs(tmp_path)
    assert not (tmp_path / "site").exists()
    page.unlink()
    with pytest.raises(ValueError, match="page is missing: index.md"):
        check_docs(tmp_path)
    config.write_text("[invalid toml")
    with pytest.raises(ValueError):
        check_docs(tmp_path)


def test_docs_check_rejects_rendered_broken_link(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/index.md").write_text("# Synthetic\n\n[Broken](missing.md)\n")
    (tmp_path / "zensical.toml").write_text(
        '[project]\nsite_name = "Synthetic"\nnav = [{"Home" = "index.md"}]\n'
    )
    with pytest.raises(subprocess.CalledProcessError):
        check_docs(tmp_path)
