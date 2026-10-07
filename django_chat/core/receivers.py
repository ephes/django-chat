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


def clear_cache_on_view_restriction_change(sender: type, **kwargs: Any) -> None:
    """Drop cached responses once a page view restriction change commits.

    The feed routes sit behind a five-minute ``cache_page``. Their restricted-
    root guard runs before the cache, but an episode restricted after the feed
    was cached would otherwise stay public, with show notes and enclosure, until
    the entry expires. Restriction changes are rare editor actions, so clearing
    the whole cache is the simple, safe choice: ``cache_page`` keys are hashed
    per URL and header set and cannot be targeted reliably.

    The clear runs on commit (production uses ``ATOMIC_REQUESTS``) so another
    worker cannot refill the cache from the pre-change state. Clearing also
    drops the feed cache generation, so a render that started before the change
    stores its response under a key nobody reads any more (see
    ``django_chat.core.feeds.restriction_aware_cache_page``).
    """
    from django.core.cache import cache
    from django.db import transaction

    transaction.on_commit(cache.clear, using=kwargs.get("using"))
