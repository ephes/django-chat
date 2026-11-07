"""Validate configured pages and render docs in a disposable directory."""

import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from urllib.parse import urlsplit


def check_docs(root: Path) -> None:
    config = tomllib.loads((root / "zensical.toml").read_text())

    docs = (root / "docs").resolve()

    def check_nav(value: object) -> None:
        if isinstance(value, str):
            url = urlsplit(value)
            if not url.scheme:
                page = (docs / url.path).resolve()
                if not page.is_relative_to(docs) or not page.is_file():
                    raise ValueError(f"Configured documentation page is missing: {value}")
        elif isinstance(value, list):
            for item in value:
                check_nav(item)
        elif isinstance(value, dict):
            for item in value.values():
                check_nav(item)

    check_nav(config["project"].get("nav", []))
    with tempfile.TemporaryDirectory(prefix="django-chat-docs-") as directory:
        project = Path(directory)
        shutil.copytree(root / "docs", project / "docs")
        shutil.copyfile(root / "zensical.toml", project / "zensical.toml")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "zensical",
                "build",
                "--strict",
                "-f",
                str(project / "zensical.toml"),
            ],
            check=True,
        )


if __name__ == "__main__":
    check_docs(Path(__file__).resolve().parents[1])
