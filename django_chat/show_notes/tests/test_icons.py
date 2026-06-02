from __future__ import annotations

import pytest
from django.template import Context, Template

from django_chat.imports.show_notes import resolve_icon_kind
from django_chat.show_notes.icons import kind_choices, snippet_for_kind


def test_snippet_for_known_kind():
    assert snippet_for_kind("links") == "links"
    assert snippet_for_kind("sale") == "sale"


def test_sponsor_aliases_share_one_snippet():
    assert snippet_for_kind("sponsor") == "sponsors"
    assert snippet_for_kind("sponsors") == "sponsors"
    assert snippet_for_kind("sponsoring_options") == "sponsors"


def test_unknown_kind_falls_back_to_default():
    assert snippet_for_kind("other") == "default"
    assert snippet_for_kind("nope") == "default"


def test_kind_choices_include_auto_first_and_other_deprecated_last():
    choices = kind_choices()
    assert choices[0] == ("auto", "Automatisch (aus Überschrift)")
    assert choices[-1] == ("other", "Other (deprecated)")
    kinds = [c[0] for c in choices]
    assert "sale" in kinds and "dashboards" in kinds and "default" in kinds


# Canonical contract for resolve_icon_kind. The picker JS matcher in
# django_chat/static/django_chat/js/icon_choice_widget.js mirrors this; keep the
# two in sync (the JS gets its rule DATA from the same Python constants).
@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("Links", "links"),
        ("🔗 Links", "links"),
        ("Support the Show", "support"),
        ("Sponsor", "sponsor"),
        ("Sponsoring Options", "sponsoring_options"),
        ("Shameless Plugs", "shameless_plugs"),
        ("Black Friday Sale", "sale"),
        ("50% Rabatt", "sale"),
        ("Special Offer", "sale"),
        ("Wholesale", "default"),
        ("Dashboard", "dashboards"),
        ("Dashboards", "dashboards"),
        ("Outro", "default"),
        ("", "default"),
    ],
)
def test_resolve_icon_kind_contract(heading: str, expected: str):
    assert resolve_icon_kind(heading) == expected


def _render(kind: str) -> str:
    tpl = Template("{% load show_note_icons %}{% show_note_icon kind %}")
    return tpl.render(Context({"kind": kind}))


def test_render_known_icon_contains_class_and_snippet():
    html = _render("sale")
    assert "show-note-icon--sale" in html
    assert "circle" in html  # the sale snippet contains <circle> elements


def test_render_unknown_icon_uses_default_snippet():
    html = _render("nope")
    assert "show-note-icon--nope" in html  # class reflects the kind verbatim
    assert "M12 17v5" in html  # default.svg (pushpin) path
