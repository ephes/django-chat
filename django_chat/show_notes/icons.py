from __future__ import annotations

from typing import NamedTuple


class IconDef(NamedTuple):
    kind: str
    label: str
    snippet: str | None  # None nur für "auto" (wird nie gerendert)


# Einzige Quelle der Wahrheit für Icon-Kinds (UI/Choices + Rendering).
# `snippet` ist vom `kind` entkoppelt: mehrere Kinds dürfen dieselbe Datei nutzen.
ICON_REGISTRY: list[IconDef] = [
    IconDef("auto", "Automatisch (aus Überschrift)", None),
    IconDef("links", "Links", "links"),
    IconDef("projects", "Projects", "projects"),
    IconDef("books", "Books", "books"),
    IconDef("youtube", "YouTube", "youtube"),
    IconDef("groups", "Groups", "groups"),
    IconDef("shameless_plugs", "Shameless Plugs", "shameless_plugs"),
    IconDef("support", "Support the Show", "support"),
    IconDef("sponsors", "Sponsors", "sponsors"),
    IconDef("sponsoring_options", "Sponsoring Options", "sponsors"),
    IconDef("sponsor", "Sponsor", "sponsors"),
    IconDef("sale", "Sale", "sale"),
    IconDef("dashboards", "Dashboards", "dashboards"),
    IconDef("default", "Default / Sonstiges", "default"),
]

DEFAULT_SNIPPET = "default"
_SNIPPET_BY_KIND = {d.kind: d.snippet for d in ICON_REGISTRY if d.snippet}


def snippet_for_kind(kind: str) -> str:
    """Snippet-Dateiname für einen kind; unbekannte/fehlende → default."""
    return _SNIPPET_BY_KIND.get(kind, DEFAULT_SNIPPET)


def kind_choices() -> list[tuple[str, str]]:
    """ChoiceBlock-Choices: alle Registry-Kinds + deprecated `other` als Fallback-Wert."""
    return [(d.kind, d.label) for d in ICON_REGISTRY] + [("other", "Other (deprecated)")]
