from __future__ import annotations

import re
from collections.abc import Iterable
from html import escape
from typing import Any, cast
from urllib.parse import urlparse
from uuid import uuid4

from bs4 import BeautifulSoup
from bs4.element import (
    CData,
    Comment,
    Declaration,
    Doctype,
    NavigableString,
    PageElement,
    ProcessingInstruction,
    Tag,
)

LIST_SECTION_HEADING_LABELS = frozenset(
    {
        "books",
        "groups",
        "links",
        "projects",
        "shameless plugs",
        "sponsors",
        "sponsoring options",
        "youtube",
    }
)
COPY_SECTION_HEADING_LABELS = frozenset({"sponsor", "support the show"})
LINK_LIST_KIND_BY_LABEL = {
    "books": "books",
    "groups": "groups",
    "links": "links",
    "projects": "projects",
    "shameless plugs": "shameless_plugs",
    "sponsors": "sponsors",
    "sponsoring options": "sponsoring_options",
    "support the show": "support",
    "youtube": "youtube",
}
CANONICAL_HEADING_BY_LABEL = {
    "books": "Books",
    "groups": "Groups",
    "links": "Links",
    "projects": "Projects",
    "shameless plugs": "Shameless Plugs",
    "sponsor": "Sponsor",
    "sponsors": "Sponsors",
    "sponsoring options": "Sponsoring Options",
    "support the show": "Support the Show",
    "youtube": "YouTube",
}
STRUCTURED_SECTION_LABELS = frozenset(LINK_LIST_KIND_BY_LABEL) | frozenset({"sponsor"})
BlockTuple = tuple[str, Any]

# Imported show-note HTML is stored as RichText block values and later rendered
# with autoescaping disabled (Wagtail's `richtext`/`expand_db_html` do NOT
# sanitize at render time — they only do so in the editor widget, which the
# importer bypasses). Everything that ends up in a stored value therefore has to
# be sanitized here, on the way in. Allowlist-based: tags not in the allowlist
# are unwrapped (their text is kept), known-dangerous container tags are dropped
# with their contents, and every attribute except a scheme-validated anchor
# `href` is removed (this strips `on*` handlers, inline `style`, etc.).
_SANITIZE_ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "a",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "code",
        "pre",
    }
)
_SANITIZE_DROP_WITH_CONTENT = frozenset(
    {
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "svg",
        "math",
        "template",
        "noscript",
        "link",
        "meta",
        "base",
        "form",
        "input",
        "textarea",
        "button",
        "select",
        "option",
        "frame",
        "frameset",
        "applet",
    }
)
_SANITIZE_ALLOWED_ATTRS: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "rel", "target", "title"}),
}


def _sanitized_href(href: Any) -> str | None:
    if not isinstance(href, str):
        return None
    candidate = href.strip()
    if candidate.lower().startswith("mailto:") and len(candidate) > len("mailto:"):
        return candidate
    return _canonical_http_url(candidate)


def sanitize_show_note_html(html: str) -> str:
    """Strip scripts, event handlers, and unsafe URL schemes from imported
    show-note HTML before it is stored and rendered without autoescaping."""
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")
    # Drop comment-like nodes. CData / Declaration / ProcessingInstruction in
    # particular matter for safety: html.parser keeps `<![CDATA[ … ]]>` as one
    # opaque node, so an embedded `<script>` is invisible to the tag passes
    # below — but a *browser* parsing an HTML (non-foreign) context treats
    # `<![CDATA[` as a bogus comment ending at the first `>`, turning whatever
    # follows into live markup (a parser-differential mXSS). Stripping these
    # nodes outright closes that gap.
    _comment_like = (CData, Comment, Declaration, Doctype, ProcessingInstruction)
    for node in soup.find_all(string=lambda text: isinstance(text, _comment_like)):
        node.extract()
    for tag in soup.find_all(
        lambda candidate: (
            bool(candidate.name) and candidate.name.lower() in _SANITIZE_DROP_WITH_CONTENT
        )
    ):
        tag.decompose()
    for tag in soup.find_all(True):
        name = (tag.name or "").lower()
        if name not in _SANITIZE_ALLOWED_TAGS:
            tag.unwrap()
            continue
        allowed = _SANITIZE_ALLOWED_ATTRS.get(name, frozenset())
        for attr in list(tag.attrs):
            if attr.lower() not in allowed:
                del tag[attr]
                continue
            if name == "a" and attr.lower() == "href":
                safe = _sanitized_href(tag.get("href"))
                if safe is None:
                    del tag[attr]
                else:
                    tag["href"] = safe
    return str(soup)


class ShowNoteStructureReport:
    def __init__(self) -> None:
        self.changed = False
        self.added_structured_block = False
        self.source_detail_blocks_restored = 0
        self.implicit_link_lists_converted = 0
        self.implicit_link_list_headings_hidden = 0
        self.implicit_link_lists_skipped = 0
        self.support_copy_sections_restored = 0
        self.raw_markdown_like = False


def normalize_show_notes_html(html: str) -> str:
    if not html:
        return html

    soup = BeautifulSoup(html, "html.parser")
    for heading in soup.find_all("h4"):
        heading.name = "h3"
    for paragraph in soup.find_all("p"):
        if _is_show_note_heading_paragraph(paragraph):
            paragraph.name = "h3"
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        _normalize_show_note_heading_text(heading)
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


def _render_legacy_markdown_notes(value: str) -> tuple[str, bool]:
    if not _looks_like_raw_markdown_notes(value):
        return value, False

    html_parts: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        if not list_items:
            return
        html_parts.append("<ul>")
        html_parts.extend(list_items)
        html_parts.append("</ul>")
        list_items.clear()

    for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if not stripped:
            flush_list()
            continue

        heading_match = re.match(r"^#{1,6}\s+(.+?)\s*$", stripped)
        if heading_match is not None:
            flush_list()
            html_parts.append(f"<h3>{_render_inline_markdown(heading_match.group(1))}</h3>")
            continue

        bullet_match = re.match(r"^[*-]\s+(.+?)\s*$", stripped)
        if bullet_match is not None:
            list_items.append(f"<li>{_render_inline_markdown(bullet_match.group(1))}</li>")
            continue

        flush_list()
        html_parts.append(f"<p>{_render_inline_markdown(stripped)}</p>")

    flush_list()
    html = "".join(html_parts)
    return html, html != value


def _render_inline_markdown(value: str) -> str:
    parts: list[str] = []
    position = 0
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", value):
        parts.append(escape(value[position : match.start()]))
        label = escape(match.group(1).strip())
        href = _sanitized_href(match.group(2).strip())
        if href is None:
            parts.append(label)
        else:
            parts.append(f'<a href="{escape(href, quote=True)}">{label}</a>')
        position = match.end()
    parts.append(escape(value[position:]))
    return "".join(parts)


def structured_show_note_detail_blocks(html: str) -> tuple[list[BlockTuple], bool]:
    """Convert safe normalized show-note sections to structured StreamField blocks."""
    blocks, report = _structured_show_note_detail_blocks(html)
    return blocks, report.changed


def _structured_show_note_detail_blocks(
    html: str,
) -> tuple[list[BlockTuple], ShowNoteStructureReport]:
    report = ShowNoteStructureReport()
    if not html:
        return [("paragraph", html)], report

    markdown_html, markdown_changed = _render_legacy_markdown_notes(html)
    report.raw_markdown_like = markdown_changed
    normalized_html = normalize_show_notes_html(markdown_html)
    soup = BeautifulSoup(normalized_html, "html.parser")
    nodes = list(soup.contents)
    blocks: list[BlockTuple] = []
    pending_nodes: list[PageElement] = []
    report.changed = markdown_changed or normalized_html != html

    index = 0
    while index < len(nodes):
        node = nodes[index]
        if _is_leading_implicit_link_list(node, pending_nodes, blocks):
            structured_block = _convert_implicit_link_list(node)
            if structured_block is not None:
                blocks.append(structured_block)
                report.changed = True
                report.added_structured_block = True
                report.implicit_link_lists_converted += 1
                report.implicit_link_list_headings_hidden += 1
                index += 1
                continue
            report.implicit_link_lists_skipped += 1

        label_key = _heading_label_key(node)
        if label_key in STRUCTURED_SECTION_LABELS:
            section_nodes: list[PageElement] = []
            index += 1
            while index < len(nodes) and not _is_heading_tag(nodes[index]):
                section_nodes.append(nodes[index])
                index += 1

            structured_block = _convert_section(label_key, section_nodes)
            if structured_block is not None:
                if _is_support_copy_section(label_key, section_nodes, structured_block):
                    report.support_copy_sections_restored += 1
                _flush_paragraph_block(pending_nodes, blocks)
                pending_nodes = []
                blocks.append(structured_block)
                report.changed = True
                report.added_structured_block = True
                continue

            if _is_support_copy_section(label_key, section_nodes, structured_block):
                report.support_copy_sections_restored += 1
            pending_nodes.append(node)
            pending_nodes.extend(section_nodes)
            continue

        pending_nodes.append(node)
        index += 1

    _flush_paragraph_block(pending_nodes, blocks)

    if not report.added_structured_block:
        return [("paragraph", sanitize_show_note_html(normalized_html))], report
    return blocks, report


def structure_episode_body_show_notes(body: Any) -> tuple[Any, bool]:
    structured_body, report = structure_episode_body_show_notes_with_report(body)
    return structured_body, report.changed


def structure_episode_body_show_notes_with_report(
    body: Any,
    *,
    source_detail_html: str = "",
) -> tuple[Any, ShowNoteStructureReport]:
    body_value = body.get_prep_value() if hasattr(body, "get_prep_value") else body
    report = ShowNoteStructureReport()
    if not isinstance(body_value, list):
        return body_value, report

    source_children: list[dict[str, Any]] | None = None
    source_report: ShowNoteStructureReport | None = None
    if source_detail_html:
        source_blocks, source_report = _structured_show_note_detail_blocks(source_detail_html)
        source_children = [_stream_child(name, value) for name, value in source_blocks]

    structured_body = []
    has_detail_block = False
    for block in body_value:
        if not isinstance(block, dict):
            structured_body.append(block)
            continue

        structured_block = dict(block)
        if structured_block.get("type") == "detail":
            has_detail_block = True
            structured_children = []
            current_body_report = ShowNoteStructureReport()
            if isinstance(structured_block.get("value"), list):
                for child in structured_block["value"]:
                    if (
                        isinstance(child, dict)
                        and child.get("type") == "paragraph"
                        and isinstance(child.get("value"), str)
                    ):
                        child_blocks, paragraph_report = _structured_show_note_detail_blocks(
                            child["value"]
                        )
                        if len(child_blocks) == 1 and child_blocks[0][0] == "paragraph":
                            value = child_blocks[0][1]
                            if value != child["value"]:
                                child = {**child, "value": value}
                            structured_children.append(child)
                        else:
                            structured_children.extend(
                                _stream_child(name, value) for name, value in child_blocks
                            )
                        _merge_structure_report(current_body_report, paragraph_report)
                        continue

                    structured_children.append(child)

            if source_children is not None:
                if not _stream_children_match_ignoring_ids(
                    structured_children,
                    source_children,
                ):
                    structured_children = source_children
                    report.changed = True
                    report.source_detail_blocks_restored += 1
                    if source_report is not None:
                        _merge_structure_report(report, source_report)
                elif current_body_report.changed:
                    _merge_structure_report(report, current_body_report)
            elif current_body_report.changed:
                _merge_structure_report(report, current_body_report)

            structured_block["value"] = structured_children

        structured_body.append(structured_block)

    if source_children is not None and not has_detail_block:
        structured_body.append(
            {
                "type": "detail",
                "value": source_children,
                "id": str(uuid4()),
            }
        )
        report.changed = True
        report.source_detail_blocks_restored += 1
        if source_report is not None:
            _merge_structure_report(report, source_report)

    return structured_body, report


def _merge_structure_report(
    target: ShowNoteStructureReport, source: ShowNoteStructureReport
) -> None:
    target.changed = target.changed or source.changed
    target.added_structured_block = target.added_structured_block or source.added_structured_block
    target.source_detail_blocks_restored += source.source_detail_blocks_restored
    target.implicit_link_lists_converted += source.implicit_link_lists_converted
    target.implicit_link_list_headings_hidden += source.implicit_link_list_headings_hidden
    target.implicit_link_lists_skipped += source.implicit_link_lists_skipped
    target.support_copy_sections_restored += source.support_copy_sections_restored
    target.raw_markdown_like = target.raw_markdown_like or source.raw_markdown_like


def _stream_children_match_ignoring_ids(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> bool:
    return _without_stream_ids(left) == _without_stream_ids(right)


def _without_stream_ids(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_stream_ids(child_value)
            for key, child_value in value.items()
            if key != "id"
        }
    if isinstance(value, list):
        return [_without_stream_ids(item) for item in value]
    return value


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


def _normalize_show_note_heading_text(heading: Any) -> None:
    if not _is_plain_text_tag(heading):
        return

    text = heading.get_text(" ", strip=True)
    cleaned_text = _strip_markdown_heading_prefix(text)
    if cleaned_text == text:
        return

    label_key = _section_label_key(cleaned_text)
    if label_key not in STRUCTURED_SECTION_LABELS:
        return

    heading.string = cleaned_text


def _strip_markdown_heading_prefix(value: str) -> str:
    match = re.match(r"^\s*#{1,6}\s*(\S.*?)\s*$", value)
    if match is None:
        return value
    return match.group(1)


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


def _heading_label_key(node: PageElement) -> str | None:
    if not _is_heading_tag(node):
        return None
    assert isinstance(node, Tag)
    label_key = _section_label_key(node.get_text(" ", strip=True))
    if not label_key or len(label_key) > 80:
        return None
    return label_key


def _is_heading_tag(node: PageElement) -> bool:
    return isinstance(node, Tag) and node.name in {"h1", "h2", "h3", "h4", "h5", "h6"}


def _is_leading_implicit_link_list(
    node: PageElement,
    pending_nodes: list[PageElement],
    blocks: list[BlockTuple],
) -> bool:
    return (
        isinstance(node, Tag)
        and node.name in {"ul", "ol"}
        and not blocks
        and not any(_node_has_meaning(pending_node) for pending_node in pending_nodes)
    )


def _is_support_copy_section(
    label_key: str,
    section_nodes: list[PageElement],
    structured_block: BlockTuple | None,
) -> bool:
    if label_key != "support the show":
        return False

    if structured_block is not None:
        name, value = structured_block
        return (
            name == "show_note_link_list"
            and isinstance(value, dict)
            and value.get("kind") == "support"
            and value.get("show_items") is False
        )

    meaningful_nodes = [node for node in section_nodes if _node_has_meaning(node)]
    if not meaningful_nodes:
        return False
    if any(isinstance(node, Tag) and node.name in {"ul", "ol"} for node in meaningful_nodes):
        return False
    if any(
        not (isinstance(node, NavigableString) or (isinstance(node, Tag) and node.name == "p"))
        for node in meaningful_nodes
    ):
        return False
    return bool(_links_from_nodes(meaningful_nodes))


def _convert_section(label_key: str, section_nodes: list[PageElement]) -> BlockTuple | None:
    if label_key == "sponsor":
        return _convert_sponsor_section(label_key, section_nodes)
    if label_key in LINK_LIST_KIND_BY_LABEL:
        return _convert_link_list_section(label_key, section_nodes)
    return None


def _convert_implicit_link_list(list_tag: PageElement) -> BlockTuple | None:
    if not isinstance(list_tag, Tag) or list_tag.name not in {"ul", "ol"}:
        return None

    items = _link_items_from_list(list_tag)
    if not items:
        return None

    return (
        "show_note_link_list",
        {
            "heading": "Links",
            "show_heading": False,
            "kind": "links",
            "intro": "",
            "items": items,
        },
    )


def _convert_sponsor_section(label_key: str, section_nodes: list[PageElement]) -> BlockTuple | None:
    content_nodes = [node for node in section_nodes if _node_has_meaning(node)]
    paragraph_nodes = [
        node
        for node in content_nodes
        if isinstance(node, NavigableString) or (isinstance(node, Tag) and node.name == "p")
    ]
    non_paragraph_nodes = [
        node
        for node in content_nodes
        if not (isinstance(node, NavigableString) or (isinstance(node, Tag) and node.name == "p"))
    ]
    if non_paragraph_nodes:
        if paragraph_nodes:
            return None
        if len(_links_from_nodes(non_paragraph_nodes)) != 1:
            return None
        if any(
            isinstance(node, Tag) and node.name in {"ul", "ol"} and not _link_items_from_list(node)
            for node in non_paragraph_nodes
        ):
            return None

    sponsor_link = _first_link(section_nodes)
    if sponsor_link is None:
        return None

    copy_html = _serialize_nodes(paragraph_nodes)
    return (
        "show_note_sponsor",
        {
            "heading": CANONICAL_HEADING_BY_LABEL[label_key],
            "sponsor_name": sponsor_link["title"],
            "sponsor_url": sponsor_link["url"],
            "copy": copy_html,
            "coupon_code": "",
        },
    )


def _convert_link_list_section(
    label_key: str, section_nodes: list[PageElement]
) -> BlockTuple | None:
    intro_nodes: list[PageElement] = []
    items: list[dict[str, Any]] = []

    for node in section_nodes:
        if not _node_has_meaning(node):
            continue
        if isinstance(node, Tag) and node.name in {"ul", "ol"}:
            list_items = _link_items_from_list(node)
            if list_items is None:
                return None
            items.extend(list_items)
        elif isinstance(node, Tag) and node.name == "p":
            intro_nodes.append(node)
        else:
            return None

    if not items:
        return None

    intro = _serialize_nodes(intro_nodes)
    show_items = True
    if label_key == "support the show" and _is_support_boilerplate_items(items):
        intro = _support_boilerplate_intro(items)
        show_items = False

    value: dict[str, Any] = {
        "heading": CANONICAL_HEADING_BY_LABEL[label_key],
        "kind": LINK_LIST_KIND_BY_LABEL[label_key],
        "intro": intro,
        "items": items,
    }
    if not show_items:
        value["show_items"] = False
    return ("show_note_link_list", value)


def _link_items_from_list(
    list_tag: Tag,
) -> list[dict[str, Any]] | None:
    items: list[dict[str, Any]] = []
    for item_tag in list_tag.find_all("li", recursive=False):
        links = _links_from_anchors(item_tag.find_all("a"))
        if not links:
            return None
        if _list_item_has_non_link_text(item_tag):
            return None
        primary_link = links[0]
        items.append(
            {
                "title": primary_link["title"],
                "url": primary_link["url"],
                "description": "",
                "extra_links": links[1:],
            }
        )
    return items


def _is_support_boilerplate_items(items: list[dict[str, Any]]) -> bool:
    if len(items) != 3:
        return False
    domains = {_support_link_domain(item.get("url", "")) for item in items}
    return domains == {"learndjango.com", "btn.dev", "django-news.com"}


def _support_boilerplate_intro(items: list[dict[str, Any]]) -> str:
    learn_url = _support_item_url(items, "learndjango.com")
    button_url = _support_item_url(items, "btn.dev")
    news_url = _support_item_url(items, "django-news.com")
    return (
        "<p>This podcast does not have any ads or sponsors. To support the show, "
        f'please consider <a href="{escape(learn_url, quote=True)}">purchasing a book</a>, '
        f'signing up for <a href="{escape(button_url, quote=True)}">Button</a>, '
        f'or reading the <a href="{escape(news_url, quote=True)}">'
        "Django News newsletter</a>.</p>"
    )


def _support_item_url(items: list[dict[str, Any]], domain: str) -> str:
    for item in items:
        url = item.get("url", "")
        if isinstance(url, str) and _support_link_domain(url) == domain:
            return url
    return ""


def _support_link_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.removeprefix("www.").casefold()


def _list_item_has_non_link_text(item_tag: Tag) -> bool:
    soup = BeautifulSoup(str(item_tag), "html.parser")
    copied_item = soup.find("li")
    if copied_item is None:
        return False

    for anchor in copied_item.find_all("a"):
        if _link_from_anchor(anchor) is None:
            anchor.unwrap()
        else:
            anchor.decompose()

    text = _linked_paragraph_title(copied_item)
    return bool(re.search(r"[\w']+", text))


def _link_item_description(item_tag: Tag) -> str:
    soup = BeautifulSoup(str(item_tag), "html.parser")
    copied_item = soup.find("li")
    if copied_item is None:
        return ""
    for anchor in copied_item.find_all("a"):
        if _link_from_anchor(anchor) is None:
            anchor.unwrap()
        else:
            anchor.decompose()

    description = _linked_paragraph_title(copied_item)
    if not description:
        return ""

    meaningful_tokens = [
        token
        for token in re.findall(r"[\w']+", description.casefold())
        if token not in {"and", "or"}
    ]
    if not meaningful_tokens:
        return ""
    return description


def _linkless_list_item_intro(item_tag: Tag) -> str:
    text = _linked_paragraph_title(item_tag)
    if not text:
        return ""
    return f"<p>{escape(text)}</p>"


def _link_items_from_nodes(nodes: Iterable[PageElement]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for node in nodes:
        if isinstance(node, Tag):
            links = _links_from_anchors(node.find_all("a"))
            if len(links) == 1:
                links[0]["title"] = _linked_paragraph_title(node) or links[0]["title"]
            items.extend(
                {
                    "title": link["title"],
                    "url": link["url"],
                    "description": "",
                    "extra_links": [],
                }
                for link in links
            )
    return items


def _links_from_nodes(nodes: Iterable[PageElement]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for node in nodes:
        if isinstance(node, Tag):
            links.extend(_links_from_anchors(node.find_all("a")))
    return links


def _linked_paragraph_title(node: Tag) -> str:
    title = node.get_text(" ", strip=True)
    return re.sub(r"\s+([,.:;!?])", r"\1", title)


def _first_link(nodes: Iterable[PageElement]) -> dict[str, str] | None:
    for node in nodes:
        if isinstance(node, Tag):
            links = _links_from_anchors(node.find_all("a"))
            if links:
                return links[0]
    return None


def _links_from_anchors(anchors: Iterable[Tag]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for anchor in anchors:
        link = _link_from_anchor(anchor)
        if link is not None:
            links.append(link)
    return links


def _link_from_anchor(anchor: Tag) -> dict[str, str] | None:
    href = anchor.get("href")
    if not isinstance(href, str):
        return None
    url = _canonical_http_url(href)
    if url is None:
        return None
    title = anchor.get_text(" ", strip=True) or url
    return {"title": title, "url": url}


def _canonical_http_url(href: str) -> str | None:
    url = href.strip()
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return url
    if parsed.scheme or url.startswith(("#", "/")):
        return None
    first_segment = url.split("/", maxsplit=1)[0]
    if "." in first_segment and " " not in first_segment:
        return f"https://{url}"
    return None


def _flush_paragraph_block(nodes: list[PageElement], blocks: list[BlockTuple]) -> None:
    html = _serialize_nodes(nodes)
    if html:
        blocks.append(("paragraph", html))


def _serialize_nodes(nodes: Iterable[PageElement]) -> str:
    html = "".join(str(node) for node in nodes if _node_has_meaning(node)).strip()
    return sanitize_show_note_html(html)


def _node_has_meaning(node: PageElement) -> bool:
    if isinstance(node, Comment):
        return False
    if isinstance(node, NavigableString):
        return bool(str(node).strip())
    return True


def _looks_like_raw_markdown_notes(html: str) -> bool:
    return bool(re.search(r"(?m)^\s*(?:[*-]\s+.*\[[^\]]+\]\([^)]+\)|#{2,6}\s+\S)", html))


def _stream_child(name: str, value: Any) -> dict[str, Any]:
    return {
        "type": name,
        "value": value,
        "id": str(uuid4()),
    }
