from __future__ import annotations

import re

from django_chat.show_notes.icons import kind_choices
from django_chat.show_notes.widgets import IconChoiceWidget


def test_widget_renders_auto_tile_and_icon_for_concrete_kind():
    widget = IconChoiceWidget(choices=kind_choices())
    html = widget.render("kind", "auto")
    assert "Auto Icon (from heading)" in html  # auto tile
    assert "show-note-icon--sale" in html  # a concrete tile renders its icon


def test_widget_preserves_option_attrs():
    widget = IconChoiceWidget(choices=kind_choices())
    html = widget.render(
        "kind",
        "auto",
        attrs={
            "id": "id_kind",
            "required": True,
            "disabled": True,
            "aria-describedby": "kind-help",
        },
    )
    assert "id_kind" in html
    assert "required" in html
    assert "disabled" in html
    assert "aria-describedby" in html


def test_widget_marks_selected_input_and_tile():
    widget = IconChoiceWidget(choices=kind_choices())
    html = widget.render("kind", "auto")
    assert "is-checked" in html
    assert 'value="auto" checked>' in html
    assert html.count(" checked>") == 1


def test_widget_preserves_telepath_placeholder_id():
    widget = IconChoiceWidget(choices=kind_choices())
    html = widget.render("kind", "auto", attrs={"id": "__ID__"})
    assert "__ID__" in html


def test_auto_option_outside_details_and_collapsed_by_default():
    widget = IconChoiceWidget(choices=kind_choices())
    html = widget.render("kind", "auto")
    assert "Auto Icon (from heading)" in html
    assert "Pick Other Icon" in html
    assert "<details" in html
    details_tag_match = re.search(r"<details([^>]*)>", html)
    assert details_tag_match is not None
    assert " open" not in details_tag_match.group(0)


def test_manual_value_opens_details():
    widget = IconChoiceWidget(choices=kind_choices())
    html = widget.render("kind", "sale")
    assert "show-note-icon--sale" in html
    assert re.search(r"<details[^>]*\sopen", html)


def test_widget_embeds_resolve_data_and_preview_slot_for_js():
    # The JS live-preview reads the rule DATA (from Python constants) off the
    # widget root and fills the auto preview slot; verify both are present.
    widget = IconChoiceWidget(choices=kind_choices())
    html = widget.render("kind", "auto")
    assert "data-icon-choice" in html
    assert "data-resolve-labels" in html
    assert "support the show" in html  # a normalized label from RESOLVE_LABEL_TO_KIND
    assert "data-auto-preview" in html
