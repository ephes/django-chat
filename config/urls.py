"""URL configuration for Django Chat."""

from cast.views import defaults as cast_default_views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.decorators.cache import cache_page
from django.views.generic import RedirectView
from django_chat.core.feeds import DjangoChatLatestEntriesFeed
from django_chat.core.views import podcast_episode_index
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
    path("", include("cast.urls", namespace="cast")),
    path("", include(wagtail_urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
