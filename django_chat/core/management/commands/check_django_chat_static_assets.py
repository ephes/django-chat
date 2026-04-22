"""Validate static asset manifests required by deployment."""

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Check Django Chat static asset manifests required for deployment."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--collected",
            action="store_true",
            help="Check collected static files under STATIC_ROOT instead of source manifests.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        collected = bool(options["collected"])
        required_paths = self._collected_paths() if collected else self._source_manifest_paths()
        missing_paths = [path for path in required_paths if not path.exists()]

        if missing_paths:
            formatted = "\n".join(f"- {path}" for path in missing_paths)
            scope = "collected static files" if collected else "source static manifests"
            msg = f"Missing required Django Chat {scope}:\n{formatted}"
            raise CommandError(msg)

        self.stdout.write(
            self.style.SUCCESS(f"Found {len(required_paths)} required static asset path(s)."),
        )

    def _source_manifest_paths(self) -> list[Path]:
        paths: list[Path] = []
        for config in settings.DJANGO_VITE.values():
            paths.append(config["manifest_path"])
        return paths

    def _collected_paths(self) -> list[Path]:
        static_root = Path(settings.STATIC_ROOT)
        paths = [static_root / "staticfiles.json"]
        for config in settings.DJANGO_VITE.values():
            static_url_prefix = config["static_url_prefix"]
            paths.append(static_root / static_url_prefix / "manifest.json")
        return paths
