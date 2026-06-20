from __future__ import annotations

import pytest
from django.urls import NoReverseMatch, reverse


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
