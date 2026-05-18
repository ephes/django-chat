from __future__ import annotations

from typing import Any, cast

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString

LIST_SECTION_HEADING_LABELS = frozenset(
    {
        "books",
        "groups",
        "links",
        "projects",
        "shameless plugs",
        "youtube",
    }
)
COPY_SECTION_HEADING_LABELS = frozenset({"sponsor", "support the show"})


def normalize_show_notes_html(html: str) -> str:
    if not html:
        return html

    soup = BeautifulSoup(html, "html.parser")
    for heading in soup.find_all("h4"):
        heading.name = "h3"
    for paragraph in soup.find_all("p"):
        if _is_show_note_heading_paragraph(paragraph):
            paragraph.name = "h3"
    return str(soup)


def normalize_episode_body_show_notes(body: Any) -> tuple[Any, bool]:
    body_value = body.get_prep_value() if hasattr(body, "get_prep_value") else body
    if not isinstance(body_value, list):
        return body_value, False

    changed = False
    normalized_body = []
    for block in body_value:
        if not isinstance(block, dict):
            normalized_body.append(block)
            continue

        normalized_block = dict(block)
        if normalized_block.get("type") == "detail" and isinstance(
            normalized_block.get("value"), list
        ):
            normalized_children = []
            for child in normalized_block["value"]:
                if (
                    isinstance(child, dict)
                    and child.get("type") == "paragraph"
                    and isinstance(child.get("value"), str)
                ):
                    normalized_html = normalize_show_notes_html(child["value"])
                    if normalized_html != child["value"]:
                        child = {**child, "value": normalized_html}
                        changed = True
                normalized_children.append(child)
            normalized_block["value"] = normalized_children

        normalized_body.append(normalized_block)

    return normalized_body, changed


def _is_show_note_heading_paragraph(paragraph: Any) -> bool:
    if not _is_plain_text_tag(paragraph):
        return False

    label = _section_label(paragraph.get_text(" ", strip=True))
    if not label or len(label) > 80:
        return False

    next_tag_name = _next_meaningful_tag_name(paragraph)
    label_key = _section_label_key(label)
    if next_tag_name in {"ul", "ol"}:
        return label_key in LIST_SECTION_HEADING_LABELS | COPY_SECTION_HEADING_LABELS
    if next_tag_name == "p":
        return label_key in COPY_SECTION_HEADING_LABELS
    return False


def _is_plain_text_tag(tag: Any) -> bool:
    return all(isinstance(child, NavigableString) for child in tag.contents)


def _next_meaningful_tag_name(tag: Any) -> str | None:
    for sibling in tag.next_siblings:
        if isinstance(sibling, Comment):
            continue
        if isinstance(sibling, NavigableString):
            if str(sibling).strip():
                return None
            continue
        return cast(str | None, getattr(sibling, "name", None))
    return None


def _section_label(value: str) -> str:
    return " ".join(value.split())


def _section_label_key(value: str) -> str:
    label = _section_label(value).removesuffix(":").casefold()
    while label and not label[0].isalnum():
        label = label[1:].lstrip()
    return label
