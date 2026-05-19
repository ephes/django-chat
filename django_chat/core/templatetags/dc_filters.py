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
def transcript_timestamp(value) -> str:
    """Trim a podlove transcript `HH:MM:SS.mmm` (or `MM:SS.mmm`) timestamp
    string to `MM:SS.D` — minute precision plus a tenth of a second.
    Hours fold into the minute count, so an episode running past one hour
    reads as `78:00.0`, not `1:18:00.0`. Returns the input untouched if
    the value isn't a recognisable timestamp."""
    if not value:
        return ""
    parts = str(value).strip().split(":")
    if len(parts) == 3:
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            secs = float(parts[2])
        except ValueError:
            return str(value)
    elif len(parts) == 2:
        hours = 0
        try:
            minutes = int(parts[0])
            secs = float(parts[1])
        except ValueError:
            return str(value)
    else:
        return str(value)
    total_minutes = hours * 60 + minutes
    return f"{total_minutes:02d}:{secs:04.1f}"


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
