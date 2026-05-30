from __future__ import annotations

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup
from django.utils.translation import gettext as _

from django_chat.imports.show_notes import _section_label_key

_SECTION_HEADINGS = ("h1", "h2", "h3", "h4")
_SPONSOR_KEY = "sponsor"

# A link whose text reads like a bare URL/domain ("sixfeetup.com",
# "www.example.com/x", "https://…") rather than a sponsor name.
_URLISH = re.compile(r"^(https?://|www\.)|^[\w-]+(\.[\w-]+)+(/.*)?$", re.IGNORECASE)


def _looks_like_url(text: str) -> bool:
    return bool(_URLISH.match(text.strip()))


def resolve_sponsor_button(
    anchors: Iterable[tuple[str, str]],
) -> tuple[str | None, str | None]:
    """Pick the CTA target and label from a sponsor paragraph's links.

    Prefers the first link whose text reads like a name → ``"Go to <name>"``.
    If only URL/domain links exist, keeps the first link but uses the neutral
    ``"Go to sponsor"``. Returns ``(None, None)`` when there are no links."""
    candidates = [(text.strip(), href) for text, href in anchors if href]
    if not candidates:
        return None, None
    for text, href in candidates:
        if text and not _looks_like_url(text):
            return href, _("Go to %(name)s") % {"name": text}
    return candidates[0][1], _("Go to sponsor")


def _find_sponsor_heading(soup: BeautifulSoup):
    for heading in soup.find_all(_SECTION_HEADINGS):
        if _section_label_key(heading.get_text(" ", strip=True)) == _SPONSOR_KEY:
            return heading
    return None


def _collect_section(heading) -> list:
    """The heading plus its following siblings up to the next section heading."""
    tags = [heading]
    for sibling in heading.find_next_siblings():
        if getattr(sibling, "name", None) in _SECTION_HEADINGS:
            break
        tags.append(sibling)
    return tags


def wrap_sponsor_shoutout(html: str) -> str:
    """Restyle a show-notes "Sponsor" section as a chat-style shout-out.

    The ``Sponsor`` heading stays in flow as an ordinary section heading; the
    paragraph(s) beneath it move into a bubble carrying a "Featured Partner of
    Django Chat" tab and — when the copy links the sponsor — a button to it.

    Preservation contract: when no sponsor section is present the input string
    is returned untouched (an exact, byte-for-byte fast path). When one *is*
    present the markup is round-tripped through the HTML parser, which preserves
    it as rendered (DOM-equivalent) but may normalise void elements
    (``<br>`` → ``<br/>``), character entities or attribute order — it never
    adds, drops or reorders content. The authored sponsor copy and every other
    section therefore render identically; only their serialisation may differ."""
    if not html or _SPONSOR_KEY not in html.lower():
        return html

    soup = BeautifulSoup(html, "html.parser")
    heading = _find_sponsor_heading(soup)
    if heading is None:
        return html

    body_tags = _collect_section(heading)[1:]
    anchors: list[tuple[str, str]] = []
    for tag in body_tags:
        for anchor in tag.find_all("a", href=True):
            anchors.append((anchor.get_text(" ", strip=True), anchor["href"]))
    url, label = resolve_sponsor_button(anchors)

    shoutout = soup.new_tag("div", attrs={"class": "sponsor-shoutout"})
    tab = soup.new_tag("span", attrs={"class": "sponsor-shoutout-tab"})
    tab.string = _("Featured Partner of Django Chat")
    msg = soup.new_tag("div", attrs={"class": "sponsor-shoutout-msg"})
    shoutout.append(tab)
    shoutout.append(msg)

    # The section heading stays put; the box is inserted right after it and the
    # original paragraph nodes are moved into the bubble unchanged (content is
    # preserved; serialisation is DOM-equivalent — see the docstring).
    heading.insert_after(shoutout)
    for tag in body_tags:
        msg.append(tag.extract())

    if url and label:
        cta = soup.new_tag(
            "a",
            href=url,
            attrs={
                "class": "sponsor-shoutout-cta",
                "rel": "noopener noreferrer",
                "target": "_blank",
            },
        )
        # The CTA reads like a podcast control: a small rounded cap on the left,
        # an audio-wave bridge in the gap, then the long field with the label +
        # arrow on the right. The cap and the wave are purely decorative; the
        # field carries the accessible label and the arrow.
        cap = soup.new_tag(
            "span", attrs={"class": "sponsor-shoutout-cta-cap", "aria-hidden": "true"}
        )
        cta.append(cap)
        wave = soup.new_tag(
            "span", attrs={"class": "sponsor-shoutout-cta-wave", "aria-hidden": "true"}
        )
        for _bar in range(5):
            wave.append(soup.new_tag("i"))
        cta.append(wave)
        field = soup.new_tag("span", attrs={"class": "sponsor-shoutout-cta-field"})
        label_span = soup.new_tag("span", attrs={"class": "sponsor-shoutout-cta-label"})
        label_span.string = label
        field.append(label_span)
        arrow = soup.new_tag(
            "span", attrs={"class": "sponsor-shoutout-cta-arrow", "aria-hidden": "true"}
        )
        arrow.string = "→"
        field.append(arrow)
        cta.append(field)
        msg.append(cta)

    return str(soup)
