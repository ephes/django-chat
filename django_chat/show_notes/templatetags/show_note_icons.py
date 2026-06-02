from __future__ import annotations

from django import template

from django_chat.show_notes.icons import snippet_for_kind

register = template.Library()


@register.inclusion_tag("cast/django_chat/show_notes/_icon.html")
def show_note_icon(kind: str) -> dict[str, str]:
    snippet = snippet_for_kind(kind)
    return {
        "kind": kind,
        "snippet_template": f"cast/django_chat/show_notes/icons/{snippet}.svg",
    }
