from __future__ import annotations

from typing import NamedTuple


class IconDef(NamedTuple):
    kind: str
    label: str
    snippet: str | None  # None only for "auto" (never rendered)


# Single source of truth for icon kinds (UI/choices + rendering).
# `snippet` is decoupled from `kind`: several kinds may reuse the same file.
ICON_REGISTRY: list[IconDef] = [
    IconDef("auto", "Auto Icon (from heading)", None),
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
    IconDef("default", "Default / Other", "default"),
]

DEFAULT_SNIPPET = "default"
_SNIPPET_BY_KIND = {d.kind: d.snippet for d in ICON_REGISTRY if d.snippet}


def snippet_for_kind(kind: str) -> str:
    """Snippet filename for a kind; unknown/missing → default."""
    return _SNIPPET_BY_KIND.get(kind, DEFAULT_SNIPPET)


def kind_choices() -> list[tuple[str, str]]:
    """ChoiceBlock choices: all registry kinds + the deprecated `other` fallback value."""
    return [(d.kind, d.label) for d in ICON_REGISTRY] + [("other", "Other (deprecated)")]
