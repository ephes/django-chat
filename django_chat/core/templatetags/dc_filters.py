from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def duration_minutes(seconds: int | None) -> str:
    """Render a duration in seconds as a `'N MIN'` label, or empty string."""
    if not seconds:
        return ""
    minutes = round(int(seconds) / 60)
    return f"{minutes} MIN"
