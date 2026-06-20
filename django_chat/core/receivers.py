"""Signal receivers for Django Chat core."""

from __future__ import annotations

from typing import Any


def reject_comment_when_disabled(
    sender: type,
    comment: Any,
    request: Any,
    **kwargs: Any,
) -> bool | None:
    """Enforce the comments-enabled gate on the server side.

    The episode template only *hides* the comment UI when comments are off, but
    the django_comments no-JS post view and the cast AJAX post view both still
    accept a direct POST. Both fire ``comment_will_be_posted`` before saving and
    drop the comment if a receiver returns ``False``, so reject here when the
    target object's ``comments_are_enabled`` gate — the global
    ``CAST_COMMENTS_ENABLED`` flag AND the per-object ``comments_enabled``
    toggles — is not satisfied. Without this, the documented opt-in gate is
    bypassable via a direct POST.
    """
    content_object = comment.content_object
    if not getattr(content_object, "comments_are_enabled", False):
        return False
    return None
