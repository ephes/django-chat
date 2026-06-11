"""Staticfiles storage helpers for Django Chat deployments."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.staticfiles import finders
from whitenoise.storage import CompressedManifestStaticFilesStorage


class MinifiedCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Minify selected CSS before manifest hashing and WhiteNoise compression."""

    def post_process(
        self,
        paths: dict[str, tuple[Any, str]],
        dry_run: bool = False,
        **options: Any,
    ) -> Any:
        if dry_run:
            yield from super().post_process(paths, dry_run=dry_run, **options)
            return

        processed_paths = dict(paths)
        for name in paths:
            if not self.should_minify_css(name):
                continue
            collected_path = Path(self.path(name))
            # Minify from the pristine finder source, not the collected copy:
            # the collected copy was overwritten with minified output on the
            # previous run, and collectstatic skips re-copying when the source
            # is unchanged — re-minifying the collected copy would keep stale
            # output alive even after the minifier itself changes.
            source_path = finders.find(name)
            css_path = Path(source_path) if isinstance(source_path, str) else collected_path
            minified = minify_css(css_path.read_text(encoding="utf-8"))
            if collected_path.is_symlink():
                collected_path.unlink()
            collected_path.write_text(minified, encoding="utf-8")
            # Django's hasher opens files from this tuple, so point it at the
            # minified collected copy rather than the readable source file.
            processed_paths[name] = (self, name)

        yield from super().post_process(processed_paths, dry_run=dry_run, **options)

    def should_minify_css(self, name: str) -> bool:
        if not getattr(settings, "DJANGO_CHAT_MINIFY_STATIC_CSS", True):
            return False
        if not name.endswith(".css"):
            return False
        if name.endswith(".min.css"):
            return False
        patterns = getattr(
            settings,
            "DJANGO_CHAT_MINIFY_STATIC_CSS_PATTERNS",
            ("django_chat/css/*.css",),
        )
        return any(fnmatch(name, pattern) for pattern in patterns)


def minify_css(css: str) -> str:
    """Return conservatively minified CSS without changing string contents."""

    return _compact_css(_strip_css_comments(css)).strip()


def _strip_css_comments(css: str) -> str:
    output: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0

    while index < len(css):
        char = css[index]

        if quote is not None:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue

        if char in {"'", '"'}:
            quote = char
            output.append(char)
            index += 1
            continue

        if char == "/" and index + 1 < len(css) and css[index + 1] == "*":
            end = css.find("*/", index + 2)
            index = len(css) if end == -1 else end + 2
            continue

        output.append(char)
        index += 1

    return "".join(output)


def _compact_css(css: str) -> str:
    # Keep unusual URLs quoted, especially data URLs; punctuation outside
    # strings is treated as normal CSS syntax and may be compacted.
    output: list[str] = []
    quote: str | None = None
    escaped = False
    pending_space = False

    for char in css:
        if quote is not None:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in {"'", '"'}:
            if pending_space and output and _needs_css_space(output[-1], char):
                output.append(" ")
            pending_space = False
            quote = char
            output.append(char)
            continue

        if char.isspace():
            pending_space = True
            continue

        if pending_space and output and _needs_css_space(output[-1], char):
            output.append(" ")
        pending_space = False

        # `:` is deliberately absent here: a preserved space before it is a
        # descendant combinator (see _needs_css_space), so it must not eat
        # the space the way `{};,` do.
        if char in "{};,":
            while output and output[-1] == " ":
                output.pop()
            if char == "}" and output and output[-1] == ";":
                output.pop()
            output.append(char)
            continue

        if output and output[-1] in "{:;,":
            while output and output[-1] == " ":
                output.pop()

        output.append(char)

    return "".join(output)


def _needs_css_space(left: str, right: str) -> bool:
    # A space before `:` or `[` can be a descendant combinator in a selector
    # (`.form :is(input)`, `html [data-x]`) or a grid line name in a value
    # (`[full-start] 1fr`); dropping it would splice a different compound
    # selector, so those characters never absorb a preceding space.
    return not (left in "{(:;,[>~" or right in "{});,>~")
