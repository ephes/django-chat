from __future__ import annotations

import re

import pytest
from django.test import Client
from django.urls import reverse

from django_chat.sponsor.models import SponsorPage


@pytest.mark.django_db
def test_sponsor_page_seeded_by_data_migration() -> None:
    """The 0002 data migration creates a singleton SponsorPage."""
    page = SponsorPage.objects.get()
    assert page.live is True
    assert page.slug == "sponsor"
    assert page.title == "Sponsor Us"
    assert page.cta_email == "will@wsvincent.com"
    assert page.slots.count() == 4
    assert [s.name for s in page.slots.all()] == [
        "Pre-roll",
        "Mid-roll",
        "Out-roll",
        "Show Notes",
    ]
    assert page.stats.count() == 4
    assert page.pricing_tiers.count() == 2
    # The source Google Doc contains five separate reviews; keep them all.
    assert page.reviews.count() == 5
    assert page.pdf is not None


@pytest.mark.django_db
def test_sponsor_page_url_reverses_to_episodes_sponsor() -> None:
    assert reverse("django_chat_sponsor") == "/episodes/sponsor/"


@pytest.mark.django_db
def test_sponsor_page_renders(client: Client) -> None:
    response = client.get(reverse("django_chat_sponsor"))

    assert response.status_code == 200
    assert "cast/django_chat/sponsor.html" in [
        template.name for template in response.templates if template.name
    ]
    content = response.content.decode()
    # Subpage header speech bubble is rendered via the shared partial.
    assert "page-header-bubble" in content
    assert "page-header-bubble-fade" in content
    assert "Sponsor Django Chat" in content
    # All four slot names from the source doc.
    for slot in ("Pre-roll", "Mid-roll", "Out-roll", "Show Notes"):
        assert slot in content
    # Pricing + CTA + note (verbatim).
    assert "Single Episode" in content
    assert "$250" in content
    assert "Five Episode Package" in content
    assert "$1,000" in content
    assert "mailto:will@wsvincent.com" in content
    assert "There is only one sponsor per episode" in content
    # Hosts bio mentions both hosts.
    assert "Will Vincent" in content
    assert "Carlton Gibson" in content
    # Reviews — every full review title from the source.
    for title in (
        "Important podcast in this space",
        "Everything interesting in Django",
        "So amazing!!",
        "Informative, engaging, and insightful",
        "Fantastic",
    ):
        assert title in content
    # PDF download surface is present and points at the Wagtail-served doc.
    assert "Download sponsorship PDF" in content
    assert "/documents/" in content
    # Wagtail appends a random suffix when MEDIA_ROOT already contains the
    # file (re-running the test DB build doesn't clean test-media), so match
    # by stem instead of exact filename.
    assert "django-chat-sponsorship-kit" in content
    assert content.count(".pdf") >= 1


@pytest.mark.django_db
def test_menu_link_overrides_google_docs_with_internal_url(client: Client) -> None:
    """The Simplecast 'Sponsor Us' link in the source fixture points to Google
    Docs. The base layout must render the internal `/episodes/sponsor/` URL
    instead (without `target="_blank"`), while leaving Fosstodon / external
    links untouched.
    """
    # Import the same sample data the live site uses so source_metadata is set.
    from django_chat.imports.import_sample import import_django_chat_sample

    import_django_chat_sample()

    response = client.get("/episodes/")
    assert response.status_code == 200
    content = response.content.decode()

    # The internal route replaces the Google-Doc URL.
    pattern = re.compile(r'<a\s+href="(?P<href>[^"]+)"(?P<attrs>[^>]*)>Sponsor Us</a>')
    match = pattern.search(content)
    assert match is not None, "Sponsor Us menu link missing from rendered base layout"
    assert match.group("href") == "/episodes/sponsor/"
    assert "target=" not in match.group("attrs")
    # The original Google Docs URL must not appear in the menu nav anymore.
    nav_section = content.split('class="site-nav"', 1)[1].split("</nav>", 1)[0]
    assert "docs.google.com" not in nav_section
