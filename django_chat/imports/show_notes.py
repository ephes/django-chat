from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, cast
from urllib.parse import urlparse
from uuid import uuid4

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, PageElement, Tag

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


def structured_show_note_detail_blocks(html: str) -> tuple[list[BlockTuple], bool]:
    """Convert safe normalized show-note sections to structured StreamField blocks."""
    if not html:
        return [("paragraph", html)], False

    normalized_html = normalize_show_notes_html(html)
    soup = BeautifulSoup(normalized_html, "html.parser")
    nodes = list(soup.contents)
    blocks: list[BlockTuple] = []
    pending_nodes: list[PageElement] = []
    changed = normalized_html != html
    added_structured_block = False

    index = 0
    while index < len(nodes):
        node = nodes[index]
        label_key = _heading_label_key(node)
        if label_key in STRUCTURED_SECTION_LABELS:
            section_nodes: list[PageElement] = []
            index += 1
            while index < len(nodes) and not _is_heading_tag(nodes[index]):
                section_nodes.append(nodes[index])
                index += 1

            structured_block = _convert_section(label_key, section_nodes)
            if structured_block is not None:
                _flush_paragraph_block(pending_nodes, blocks)
                pending_nodes = []
                blocks.append(structured_block)
                changed = True
                added_structured_block = True
                continue

            pending_nodes.append(node)
            pending_nodes.extend(section_nodes)
            continue

        pending_nodes.append(node)
        index += 1

    _flush_paragraph_block(pending_nodes, blocks)

    if not added_structured_block:
        return [("paragraph", normalized_html)], changed
    return blocks, changed


def structure_episode_body_show_notes(body: Any) -> tuple[Any, bool]:
    body_value = body.get_prep_value() if hasattr(body, "get_prep_value") else body
    if not isinstance(body_value, list):
        return body_value, False

    changed = False
    structured_body = []
    for block in body_value:
        if not isinstance(block, dict):
            structured_body.append(block)
            continue

        structured_block = dict(block)
        if structured_block.get("type") == "detail" and isinstance(
            structured_block.get("value"), list
        ):
            structured_children = []
            for child in structured_block["value"]:
                if (
                    isinstance(child, dict)
                    and child.get("type") == "paragraph"
                    and isinstance(child.get("value"), str)
                ):
                    child_blocks, child_changed = structured_show_note_detail_blocks(child["value"])
                    if len(child_blocks) == 1 and child_blocks[0][0] == "paragraph":
                        value = child_blocks[0][1]
                        if value != child["value"]:
                            child = {**child, "value": value}
                        structured_children.append(child)
                    else:
                        structured_children.extend(
                            _stream_child(name, value) for name, value in child_blocks
                        )
                    changed = changed or child_changed
                    continue

                structured_children.append(child)

            structured_block["value"] = structured_children

        structured_body.append(structured_block)

    return structured_body, changed


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


def _convert_section(label_key: str, section_nodes: list[PageElement]) -> BlockTuple | None:
    if label_key == "sponsor":
        return _convert_sponsor_section(label_key, section_nodes)
    if label_key in LINK_LIST_KIND_BY_LABEL:
        return _convert_link_list_section(label_key, section_nodes)
    return None


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

    paragraph_support = not items and label_key == "support the show"
    if paragraph_support:
        items = _link_items_from_nodes(intro_nodes)
    if not items:
        return None

    return (
        "show_note_link_list",
        {
            "heading": CANONICAL_HEADING_BY_LABEL[label_key],
            "kind": LINK_LIST_KIND_BY_LABEL[label_key],
            "intro": "" if paragraph_support else _serialize_nodes(intro_nodes),
            "items": items,
        },
    )


def _link_items_from_list(list_tag: Tag) -> list[dict[str, Any]] | None:
    items: list[dict[str, Any]] = []
    for item_tag in list_tag.find_all("li", recursive=False):
        links = _links_from_anchors(item_tag.find_all("a"))
        if not links:
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
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        url = _canonical_http_url(href)
        if url is None:
            continue
        title = anchor.get_text(" ", strip=True) or url
        links.append({"title": title, "url": url})
    return links


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
    return "".join(str(node) for node in nodes if _node_has_meaning(node)).strip()


def _node_has_meaning(node: PageElement) -> bool:
    if isinstance(node, Comment):
        return False
    if isinstance(node, NavigableString):
        return bool(str(node).strip())
    return True


def _stream_child(name: str, value: Any) -> dict[str, Any]:
    return {
        "type": name,
        "value": value,
        "id": str(uuid4()),
    }
