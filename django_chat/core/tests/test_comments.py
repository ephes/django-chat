from __future__ import annotations

import django_comments
import pytest
from cast.models import Episode
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.test import Client, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django_comments.models import Comment

from django_chat.imports.import_sample import import_django_chat_sample

EPISODE_SLUG = "django-tasks-jake-howard"


def _comment_post_data(target: object, **overrides: str) -> dict[str, str]:
    # django_comments needs valid security fields (content_type/object_pk/
    # timestamp/security_hash) to accept a POST; generate them for the target.
    security = django_comments.get_form()(target).generate_security_data()
    return {
        **security,
        "name": "Spammer",
        "email": "spammer@example.com",
        "comment": "Direct POST bypass attempt.",
        "honeypot": "",
        **overrides,
    }


def _episode_detail_path() -> str:
    return f"/{settings.DJANGO_CHAT_PODCAST_SLUG}/{EPISODE_SLUG}/"


def _enable_comments_on_imported_episode() -> None:
    # The Django Chat importer ships podcast comments off, but imported episodes
    # on. Enabling the podcast page mirrors the normal operator workflow:
    # global CAST_COMMENTS_ENABLED flag AND blog.comments_enabled.
    episode = Episode.objects.get(slug=EPISODE_SLUG)
    blog = episode.blog
    blog.comments_enabled = True
    blog.save(update_fields=["comments_enabled"])


def _create_public_comment(episode: Episode, text: str = "A comment I wrote.") -> Comment:
    # Build a public, top-level comment directly so author-edit eligibility
    # (public, not removed, unanswered) is deterministic and does not depend on
    # the moderation/spam outcome of a posted comment.
    comment_model = django_comments.get_model()
    return comment_model.objects.create(
        content_type=ContentType.objects.get_for_model(episode),
        object_pk=str(episode.pk),
        site=Site.objects.get_current(),
        user_name="Commenter",
        user_email="commenter@example.com",
        comment=text,
        submit_date=timezone.now(),
        is_public=True,
        is_removed=False,
    )


def _own_comment_in_session(client: Client, comment: Comment) -> None:
    # django-cast tracks comment ownership server-side in the session under
    # ``cast_owned_comments`` (never client-supplied). Seed it so the GET below
    # renders the page as the comment's author.
    session = client.session
    session["cast_owned_comments"] = [str(comment.pk)]
    session.save()


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


def test_comment_posted_page_uses_site_shell() -> None:
    # preview.html/posted.html extend comments/base.html; our override makes
    # that the Django Chat site shell instead of cast's bare page.
    html = render_to_string("comments/posted.html", {"next": "/episodes/"})
    assert 'class="site-header"' in html
    assert "Django Chat" in html


@pytest.mark.django_db
def test_no_js_post_rejected_when_comments_globally_disabled(client: Client) -> None:
    # The episode template only HIDES the UI when comments are off; the post
    # endpoint must also refuse to create a comment server-side. Here the
    # per-object toggles are on but the global CAST_COMMENTS_ENABLED flag is off
    # (default), so comments_are_enabled is False and the POST must be rejected.
    import_django_chat_sample()
    _enable_comments_on_imported_episode()
    episode = Episode.objects.get(slug=EPISODE_SLUG)
    comment_model = django_comments.get_model()
    before = comment_model.objects.count()

    response = client.post(reverse("comments-post-comment"), _comment_post_data(episode))

    assert response.status_code == 400
    assert comment_model.objects.count() == before


@pytest.mark.django_db
@override_settings(CAST_COMMENTS_ENABLED=True)
def test_ajax_post_rejected_when_comments_disabled_per_object(client: Client) -> None:
    # Global flag and podcast switch on, but this specific episode is opted out,
    # so the AJAX post endpoint must reject a direct POST too.
    import_django_chat_sample()
    episode = Episode.objects.get(slug=EPISODE_SLUG)
    blog = episode.blog
    blog.comments_enabled = True
    blog.save(update_fields=["comments_enabled"])
    episode.comments_enabled = False
    episode.save(update_fields=["comments_enabled"])
    comment_model = django_comments.get_model()
    before = comment_model.objects.count()

    response = client.post(
        reverse("comments-post-comment-ajax"),
        _comment_post_data(episode),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 400
    assert comment_model.objects.count() == before


@pytest.mark.django_db
@override_settings(CAST_COMMENTS_ENABLED=True)
def test_ajax_post_accepted_when_comments_enabled(client: Client) -> None:
    # The server-side gate must not over-reject: with the global flag and both
    # per-object toggles on, a valid POST still creates a comment.
    import_django_chat_sample()
    _enable_comments_on_imported_episode()
    episode = Episode.objects.get(slug=EPISODE_SLUG)
    comment_model = django_comments.get_model()
    before = comment_model.objects.count()

    response = client.post(
        reverse("comments-post-comment-ajax"),
        _comment_post_data(episode),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    assert comment_model.objects.count() == before + 1


def test_author_edit_delete_urls_are_mounted() -> None:
    # The local comment.html override reverses these names for the edit/delete
    # data attributes; a missing include would 500 an enabled, owned comment.
    assert reverse("comments-edit-comment-ajax") == "/comments/edit/ajax/"
    assert reverse("comments-delete-comment-ajax") == "/comments/delete/ajax/"


@pytest.mark.django_db
@override_settings(CAST_COMMENTS_ENABLED=True, CAST_COMMENTS_ALLOW_AUTHOR_EDITS=True)
def test_author_controls_render_for_own_comment(client: Client) -> None:
    # With the feature on and the session owning a public, unanswered comment,
    # the edit/delete controls + hidden raw source render in our local template.
    import_django_chat_sample()
    _enable_comments_on_imported_episode()
    episode = Episode.objects.get(slug=EPISODE_SLUG)
    comment = _create_public_comment(episode)
    _own_comment_in_session(client, comment)

    content = client.get(_episode_detail_path()).content.decode()
    assert "comment-edit-link" in content
    assert "comment-delete-link" in content
    assert 'data-edit-action="/comments/edit/ajax/"' in content
    assert 'data-delete-action="/comments/delete/ajax/"' in content
    # The inline editor reads the raw (un-linebroken) text from this hidden node.
    assert 'class="comment-raw"' in content


@pytest.mark.django_db
@override_settings(CAST_COMMENTS_ENABLED=True, CAST_COMMENTS_ALLOW_AUTHOR_EDITS=False)
def test_author_controls_absent_when_feature_disabled(client: Client) -> None:
    # Same owned, public comment, but the feature flag is off: no author controls
    # and no raw source should render (comment_action_context early-returns).
    import_django_chat_sample()
    _enable_comments_on_imported_episode()
    episode = Episode.objects.get(slug=EPISODE_SLUG)
    comment = _create_public_comment(episode)
    _own_comment_in_session(client, comment)

    content = client.get(_episode_detail_path()).content.decode()
    assert "comment-edit-link" not in content
    assert "comment-delete-link" not in content
    assert 'class="comment-raw"' not in content


@pytest.mark.django_db
@override_settings(CAST_COMMENTS_ENABLED=True, CAST_COMMENTS_ALLOW_AUTHOR_EDITS=True)
def test_author_controls_absent_for_comment_not_owned(client: Client) -> None:
    # The feature is on and the comment is public, but the session does not own
    # it (no ownership seeded), so a different visitor sees no edit/delete links.
    import_django_chat_sample()
    _enable_comments_on_imported_episode()
    episode = Episode.objects.get(slug=EPISODE_SLUG)
    _create_public_comment(episode)

    content = client.get(_episode_detail_path()).content.decode()
    assert "comment-edit-link" not in content
    assert "comment-delete-link" not in content
