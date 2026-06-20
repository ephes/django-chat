from __future__ import annotations

import pytest
from cast.models import Episode
from django.conf import settings
from django.test import Client, override_settings
from django.urls import NoReverseMatch, reverse

from django_chat.imports.import_sample import import_django_chat_sample

EPISODE_SLUG = "django-tasks-jake-howard"


def _episode_detail_path() -> str:
    return f"/{settings.DJANGO_CHAT_PODCAST_SLUG}/{EPISODE_SLUG}/"


def _enable_comments_on_imported_episode() -> None:
    # The Django Chat importer ships the podcast and episodes with
    # comments_enabled=False (comments are opt-in per object). Turning them on
    # mirrors the operator workflow of the enablement chain: the global
    # CAST_COMMENTS_ENABLED flag AND blog.comments_enabled AND post.comments_enabled.
    episode = Episode.objects.get(slug=EPISODE_SLUG)
    blog = episode.blog
    blog.comments_enabled = True
    blog.save(update_fields=["comments_enabled"])
    episode.comments_enabled = True
    episode.save(update_fields=["comments_enabled"])


def test_comment_urls_are_mounted() -> None:
    # Enabling comments renders templates that reverse these names; if they are
    # not mounted, an enabled comment page 500s.
    assert reverse("comments-post-comment-ajax") == "/comments/post/ajax/"
    # The no-JS POST path needs the standard django_comments post + done URLs
    # (post -> redirect to the "comment posted" page). A misconfigured include
    # could mount the AJAX endpoint but omit these, so assert each explicitly.
    for name in ("comments-post-comment", "comments-comment-done"):
        try:
            reverse(name)
        except NoReverseMatch:  # pragma: no cover - failure path
            pytest.fail(f"django_comments URL {name!r} is not included under comments/")


@pytest.mark.django_db
def test_comments_section_absent_when_flag_disabled(client: Client) -> None:
    import_django_chat_sample()
    content = client.get(_episode_detail_path()).content.decode()
    assert 'class="comments-section' not in content
    assert "js-comments-form" not in content
    assert "fluent_comments/js/ajaxcomments.js" not in content


@pytest.mark.django_db
@override_settings(CAST_COMMENTS_ENABLED=True)
def test_comments_section_renders_django_chat_markup_when_enabled(client: Client) -> None:
    import_django_chat_sample()
    _enable_comments_on_imported_episode()
    response = client.get(_episode_detail_path())
    assert response.status_code == 200  # not a 500 from a missing reverse
    content = response.content.decode()
    # Section + JS/AJAX contract preserved
    assert 'class="comments-section' in content
    assert 'class="js-comments-form' in content
    assert 'data-ajax-action="/comments/post/ajax/"' in content
    assert "fluent_comments/js/ajaxcomments.js" in content
    # Our crispy-free fields
    assert 'name="name"' in content
    assert 'name="email"' in content
    assert 'name="comment"' in content
    assert 'name="honeypot"' in content
    # Identity is name/email only (spec): url/title are excluded from the form.
    assert 'name="url"' not in content
    assert 'name="title"' not in content
    # Bootstrap/crispy markup is gone (proves the override replaced the default)
    assert "form-horizontal" not in content
    assert "col-sm-" not in content
