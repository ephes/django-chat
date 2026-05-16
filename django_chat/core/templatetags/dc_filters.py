from __future__ import annotations

from types import SimpleNamespace

from django import template
from django.templatetags.static import static

register = template.Library()


_PLATFORM_ICON_SLUGS = {
    "apple podcasts": "apple-podcasts",
    "overcast": "overcast",
    "pocketcast": "pocket-casts",
    "pocket casts": "pocket-casts",
    "youtube": "youtube",
    "spotify": "spotify",
    "amazon music and audible": "amazon-music",
    "amazon music": "amazon-music",
    "audible": "audible",
}


_COMBINED_AMAZON_AUDIBLE_NAME = "Amazon Music and Audible"
_AMAZON_MUSIC_DISPLAY_NAME = "Amazon Music"
_AUDIBLE_DISPLAY_NAME = "Audible"
_AUDIBLE_URL = (
    "https://www.audible.de/podcast/Django-Chat/B08JKRSG27"
    "?source_code=ASSGB149080119000H&share_location=pdp"
)


@register.filter
def duration_minutes(seconds: int | None) -> str:
    """Render a duration in seconds as a `'N MIN'` label, or empty string."""
    if not seconds:
        return ""
    minutes = round(int(seconds) / 60)
    return f"{minutes} MIN"


@register.filter
def platform_icon(name) -> str:
    """Return the static URL of the platform-icon SVG for the given name, or empty string."""
    if not isinstance(name, str):
        return ""
    slug = _PLATFORM_ICON_SLUGS.get(name.strip().lower())
    if not slug:
        return ""
    return static(f"django_chat/img/platforms/{slug}.svg")


@register.filter
def youtube_first(links):
    """Reorder a distribution-link iterable so the YouTube entry comes first."""
    items = list(links)
    for i, link in enumerate(items):
        if getattr(link, "name", None) == "YouTube":
            if i == 0:
                return items
            return [items[i], *items[:i], *items[i + 1 :]]
    return items


@register.filter
def split_amazon_audible(links):
    """Split the combined "Amazon Music and Audible" entry into two display links."""
    result = []
    for link in links:
        if getattr(link, "name", None) == _COMBINED_AMAZON_AUDIBLE_NAME:
            amazon_url = getattr(link, "url", "")
            result.append(SimpleNamespace(name=_AMAZON_MUSIC_DISPLAY_NAME, url=amazon_url))
            result.append(SimpleNamespace(name=_AUDIBLE_DISPLAY_NAME, url=_AUDIBLE_URL))
        else:
            result.append(link)
    return result
