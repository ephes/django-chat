from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from django_chat.core.sponsor_shoutout import (
    resolve_sponsor_button,
    wrap_sponsor_shoutout,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


SPONSOR_SECTION = (
    "<h3>\U0001f91d Sponsor</h3>"
    "<p>This episode was brought to you by "
    '<a href="https://buttondown.com/django">Buttondown</a>, the easiest way '
    "to start, send, and grow your email newsletter.</p>"
)


# ---- detector: only act when a sponsor section is present ----


def test_no_sponsor_section_is_returned_unchanged():
    html = "<h3>\U0001f517 Links</h3><ul><li>a</li></ul>"
    assert wrap_sponsor_shoutout(html) == html


def test_support_the_show_gets_icon_without_shoutout():
    html = "<h3>Support the show</h3><p>Back us on Patreon.</p>"
    soup = _soup(wrap_sponsor_shoutout(html))

    assert soup.select_one(".sponsor-shoutout") is None
    support_heading = soup.find("h3")
    assert support_heading is not None
    assert support_heading.get_text(" ", strip=True) == "Support the show"
    assert support_heading.select_one(".show-note-icon--support") is not None
    assert "Back us on Patreon." in soup.get_text()


def test_support_the_show_icon_is_not_duplicated():
    html = (
        '<h3><span class="show-note-icon show-note-icon--support" '
        'aria-hidden="true"></span>Support the Show</h3>'
        "<p>Back us on Patreon.</p>"
    )

    soup = _soup(wrap_sponsor_shoutout(html))

    assert len(soup.select(".show-note-icon--support")) == 1


# ---- structure: heading stays in flow, body becomes the shout-out ----


def test_sponsor_section_becomes_a_shoutout():
    soup = _soup(wrap_sponsor_shoutout(SPONSOR_SECTION))
    shoutout = soup.select_one(".sponsor-shoutout")
    assert shoutout is not None
    tab = shoutout.select_one(".sponsor-shoutout-tab")
    assert tab is not None
    assert "Featured Partner of Django Chat" in tab.get_text()
    msg = shoutout.select_one(".sponsor-shoutout-msg")
    assert msg is not None
    assert msg.find("p") is not None
    assert "brought to you by" in msg.get_text()


def test_heading_stays_outside_the_shoutout_as_section_heading():
    soup = _soup(wrap_sponsor_shoutout(SPONSOR_SECTION))
    shoutout = soup.select_one(".sponsor-shoutout")
    assert shoutout is not None
    # the section heading is NOT pulled into the box; it stays a peer heading
    assert shoutout.find("h3") is None
    headings = [h for h in soup.find_all("h3") if "Sponsor" in h.get_text()]
    assert len(headings) == 1


def test_other_sections_stay_outside_the_shoutout():
    html = "<h3>\U0001f517 Links</h3><ul><li>x</li></ul>" + SPONSOR_SECTION
    soup = _soup(wrap_sponsor_shoutout(html))
    shoutout = soup.select_one(".sponsor-shoutout")
    assert shoutout is not None
    assert "Links" not in shoutout.get_text()
    assert any("Links" in h.get_text() for h in soup.find_all("h3"))


def test_section_boundary_stops_at_next_heading():
    html = SPONSOR_SECTION + "<h3>\U0001f4da Books</h3><ul><li>b</li></ul>"
    soup = _soup(wrap_sponsor_shoutout(html))
    shoutout = soup.select_one(".sponsor-shoutout")
    assert shoutout is not None
    assert "Books" not in shoutout.get_text()


# ---- button: surfaced from the sponsor link ----


def test_button_uses_sponsor_link_and_name():
    soup = _soup(wrap_sponsor_shoutout(SPONSOR_SECTION))
    cta = soup.select_one(".sponsor-shoutout-msg a.sponsor-shoutout-cta")
    assert cta is not None
    assert cta["href"] == "https://buttondown.com/django"
    assert "Go to Buttondown" in cta.get_text()


def test_no_link_means_no_button():
    html = "<h3>\U0001f91d Sponsor</h3><p>Thanks to our sponsor this week.</p>"
    soup = _soup(wrap_sponsor_shoutout(html))
    assert soup.select_one(".sponsor-shoutout") is not None
    assert soup.select_one("a.sponsor-shoutout-cta") is None


# ---- preservation: nothing else is dropped/reordered (DOM-equivalent) ----


def test_non_sponsor_markup_survives_the_round_trip():
    other = (
        "<h3>\U0001f517 Links</h3>"
        "<p>A &amp; B<br>line two, "
        '<a href="https://example.com/x" rel="noopener noreferrer">a link</a>.</p>'
    )
    soup = _soup(wrap_sponsor_shoutout(other + SPONSOR_SECTION))
    link = soup.find("a", href="https://example.com/x")
    assert link is not None
    assert link.get_text() == "a link"
    assert link.get("rel") == ["noopener", "noreferrer"]
    assert soup.find("br") is not None
    assert "A & B" in soup.get_text()


def test_sponsor_copy_is_preserved_in_the_box():
    msg = _soup(wrap_sponsor_shoutout(SPONSOR_SECTION)).select_one(".sponsor-shoutout-msg")
    assert msg is not None
    assert "the easiest way to start, send, and grow your email newsletter" in msg.get_text()
    assert msg.find("a", href="https://buttondown.com/django") is not None


# ---- link/name heuristic (unit) ----


def test_resolve_button_prefers_name_over_bare_domain():
    anchors = [
        ("sixfeetup.com", "https://sixfeetup.com/"),
        ("Six Feet Up", "https://sixfeetup.com/"),
    ]
    url, label = resolve_sponsor_button(anchors)
    assert url == "https://sixfeetup.com/"
    assert label == "Go to Six Feet Up"


def test_resolve_button_falls_back_to_neutral_for_domain_only():
    anchors = [("sixfeetup.com", "https://sixfeetup.com/")]
    url, label = resolve_sponsor_button(anchors)
    assert url == "https://sixfeetup.com/"
    assert label == "Go to sponsor"


def test_resolve_button_handles_plain_name():
    anchors = [("Buttondown", "https://buttondown.com/django")]
    assert resolve_sponsor_button(anchors) == (
        "https://buttondown.com/django",
        "Go to Buttondown",
    )


def test_resolve_button_none_without_links():
    assert resolve_sponsor_button([]) == (None, None)


@pytest.mark.parametrize(
    "text",
    ["https://example.com", "www.example.com", "example.com/path", "EXAMPLE.COM"],
)
def test_urlish_link_text_is_treated_as_domain(text):
    _url, label = resolve_sponsor_button([(text, "https://example.com")])
    assert label == "Go to sponsor"


# ---- template tag ----


def _render(inner: str) -> str:
    from django.template import Context, Template

    return Template(
        "{% load dc_sponsor %}{% sponsor_shoutout %}" + inner + "{% endsponsor_shoutout %}"
    ).render(Context())


def test_templatetag_wraps_sponsor_section():
    out = _render(SPONSOR_SECTION)
    assert "sponsor-shoutout" in out
    assert "Featured Partner of Django Chat" in out


def test_templatetag_passes_non_sponsor_through_unchanged():
    out = _render("<h3>\U0001f517 Links</h3><ul><li>x</li></ul>")
    assert "sponsor-shoutout" not in out
    assert "Links" in out
