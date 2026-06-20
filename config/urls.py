"""URL configuration for Django Chat."""

from cast.views import defaults as cast_default_views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.decorators.cache import cache_page
from django.views.generic import RedirectView
from django_chat.core.feeds import DjangoChatLatestEntriesFeed
from django_chat.core.views import episode_embed, podcast_episode_index
from django_chat.sponsor.views import sponsor_page
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

handler400 = cast_default_views.bad_request
handler403 = cast_default_views.permission_denied
handler404 = cast_default_views.page_not_found
handler500 = cast_default_views.server_error

urlpatterns = [
    path(
        "",
        RedirectView.as_view(url=f"/{settings.DJANGO_CHAT_PODCAST_SLUG}/", permanent=False),
        name="home",
    ),
    path(settings.ADMIN_URL, admin.site.urls),
    path(settings.DJANGO_CHAT_WAGTAIL_ADMIN_PATH, include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    # Mounted before the cast/wagtail catch-all includes below so the comment
    # endpoints reverse (and resolve) instead of being swallowed by Wagtail's
    # page router.
    path("comments/", include("cast.comments.urls")),
    path(
        f"{settings.DJANGO_CHAT_PODCAST_SLUG}/",
        podcast_episode_index,
        name="django_chat_episode_index",
    ),
    path(
        f"{settings.DJANGO_CHAT_PODCAST_SLUG}/feed/rss.xml",
        cache_page(5 * 60)(DjangoChatLatestEntriesFeed()),
        {"slug": settings.DJANGO_CHAT_PODCAST_SLUG},
        name="django_chat_latest_entries_feed",
    ),
    path(
        f"{settings.DJANGO_CHAT_PODCAST_SLUG}/sponsor/",
        sponsor_page,
        name="django_chat_sponsor",
    ),
    path(
        f"{settings.DJANGO_CHAT_PODCAST_SLUG}/<slug:episode_slug>/embed/",
        episode_embed,
        name="django_chat_episode_embed",
    ),
    # Optional friendly alias for the canonical generated podcast feed. It is a
    # convenience redirect only; the canonical feed URL stays the django-cast
    # route and is what directories and `itunes:new-feed-url` must point at.
    path(
        "feed/rss.xml",
        RedirectView.as_view(
            url=reverse_lazy(
                "cast:podcast_feed_rss",
                args=[settings.DJANGO_CHAT_PODCAST_SLUG, "mp3"],
            ),
            permanent=True,
        ),
        name="django_chat_feed_alias",
    ),
    path("", include("cast.urls", namespace="cast")),
    path("", include(wagtail_urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
