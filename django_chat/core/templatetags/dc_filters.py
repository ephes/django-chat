from __future__ import annotations

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
    "amazon music and audible": "audible",
    "audible": "audible",
}


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
