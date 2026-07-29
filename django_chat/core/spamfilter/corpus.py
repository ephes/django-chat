"""Extract a labelled comment corpus from a python-podcast PostgreSQL dump.

Reading a dump rather than python-podcast's live database keeps the training
pipeline off a production host. The labels mirror
`cast.models.moderation.SpamFilter.get_training_data_comments` so the corpus
matches what django-cast itself would build:

    label   = "ham" if (is_public and not is_removed) else "spam"
    message = f"{name} {email} {title} {comment}"

The comment model is a proxy over `threadedcomments.ThreadedComment`, which uses
multi-table inheritance, so `title` lives in `threadedcomments_comment` while the
remaining fields live in `django_comments` — both tables are needed.
"""

from __future__ import annotations

import gzip
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import IO

LabelledMessage = tuple[str, str]

COMMENTS_TABLE = "django_comments"
THREADED_TABLE = "threadedcomments_comment"
AUTHOR_META_TABLE = "cast_comments_commentauthormeta"

REQUIRED_TABLES = (COMMENTS_TABLE, THREADED_TABLE)
WANTED_TABLES = frozenset((COMMENTS_TABLE, THREADED_TABLE, AUTHOR_META_TABLE))

# PostgreSQL COPY text format escapes.
_UNESCAPE = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", "b": "\b", "f": "\f", "v": "\v"}

_NULL = "\\N"


class CorpusError(RuntimeError):
    """Raised when a dump does not contain a usable comment corpus."""


def _unescape(field: str) -> str | None:
    """Decode one COPY-format field. Returns None for SQL NULL."""
    if field == _NULL:
        return None
    if "\\" not in field:
        return field
    out: list[str] = []
    index = 0
    length = len(field)
    while index < length:
        char = field[index]
        if char == "\\" and index + 1 < length:
            replacement = _UNESCAPE.get(field[index + 1])
            if replacement is not None:
                out.append(replacement)
                index += 2
                continue
        out.append(char)
        index += 1
    return "".join(out)


def _open_dump(path: Path) -> IO[str]:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def _parse_copy_header(line: str) -> tuple[str, list[str]] | None:
    """Parse a `COPY public.<table> (<cols>) FROM stdin;` header line."""
    if not line.startswith("COPY "):
        return None
    body = line[len("COPY ") :]
    table = body.split(" ", 1)[0]
    if table.startswith("public."):
        table = table[len("public.") :]
    if "(" not in body or ")" not in body:
        return None
    columns = [
        column.strip().strip('"') for column in body[body.index("(") + 1 : body.index(")")].split(",")
    ]
    return table, columns


def iter_copy_blocks(
    path: Path, wanted: frozenset[str] | None = None
) -> Iterator[tuple[str, list[dict[str, str | None]]]]:
    """Yield `(table, rows)` for each COPY block in the dump.

    Rows are dicts keyed by column name. Only tables in `wanted` are
    materialised, so a full dump does not have to fit in memory.
    """
    with _open_dump(path) as handle:
        table: str | None = None
        columns: list[str] = []
        rows: list[dict[str, str | None]] = []
        collecting = False
        for line in handle:
            if table is None:
                header = _parse_copy_header(line)
                if header is None:
                    continue
                table, columns = header
                rows = []
                collecting = wanted is None or table in wanted
                continue
            if line.startswith("\\."):
                if collecting:
                    yield table, rows
                table = None
                continue
            if not collecting:
                continue
            fields = line.rstrip("\n").split("\t")
            rows.append(dict(zip(columns, (_unescape(field) for field in fields), strict=False)))


def load_tables(path: Path) -> dict[str, list[dict[str, str | None]]]:
    """Read the comment-related tables out of the dump."""
    tables: dict[str, list[dict[str, str | None]]] = {}
    for table, rows in iter_copy_blocks(path, WANTED_TABLES):
        tables[table] = rows
        if WANTED_TABLES.issubset(tables):
            break
    missing = [table for table in REQUIRED_TABLES if table not in tables]
    if missing:
        raise CorpusError(f"{path}: dump is missing required table(s): {', '.join(missing)}")
    return tables


def extract_comment_corpus(path: Path) -> list[LabelledMessage]:
    """Build the labelled `(label, message)` corpus from a python-podcast dump."""
    tables = load_tables(path)
    titles = {
        row["comment_ptr_id"]: row.get("title") or "" for row in tables[THREADED_TABLE]
    }
    # Author-deleted comments are excluded entirely: a legitimate comment the
    # author removed must not be labelled spam and poison the filter. This
    # mirrors SpamFilter.get_training_data_comments.
    deleted = {
        row["comment_pk"]
        for row in tables.get(AUTHOR_META_TABLE, [])
        if row.get("deleted_at")
    }

    corpus: list[LabelledMessage] = []
    for row in tables[COMMENTS_TABLE]:
        if row["id"] in deleted:
            continue
        is_public = row["is_public"] == "t"
        is_removed = row["is_removed"] == "t"
        label = "ham" if (is_public and not is_removed) else "spam"
        message = " ".join(
            (
                row.get("user_name") or "",
                row.get("user_email") or "",
                titles.get(row["id"], ""),
                row.get("comment") or "",
            )
        )
        corpus.append((label, message))

    if not corpus:
        raise CorpusError(f"{path}: dump contained no comments")
    return corpus


def label_counts(corpus: list[LabelledMessage]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for label, _message in corpus:
        counts[label] += 1
    return dict(counts)
