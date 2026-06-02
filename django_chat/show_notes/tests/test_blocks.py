from __future__ import annotations

from django_chat.show_notes.blocks import (
    ShowNoteHeadingBlock,
    ShowNoteLinkListBlock,
    ShowNoteSponsorBlock,
    heading_block,
)


def _display(block, value):
    """Render-time icon kind exposed to the template."""
    return block.get_context(block.to_python(value))["display_kind"]


def test_link_list_display_resolves_from_heading_when_icon_absent():
    block = ShowNoteLinkListBlock()
    value = {"heading": "Black Friday Sale", "kind": "auto", "intro": "", "items": [], "icon": ""}
    assert _display(block, value) == "sale"


def test_explicit_kind_display_when_icon_absent():
    block = ShowNoteLinkListBlock()
    value = {"heading": "Black Friday Sale", "kind": "books", "intro": "", "items": [], "icon": ""}
    assert _display(block, value) == "books"


def test_display_prefers_stored_icon():
    block = ShowNoteHeadingBlock()
    # A materialized icon wins over re-deriving from the heading.
    assert _display(block, {"heading": "Outro", "kind": "auto", "icon": "sale"}) == "sale"


def test_display_falls_back_when_icon_key_missing():
    block = ShowNoteHeadingBlock()
    # Simulates old/un-migrated JSON that has no `icon` field at all.
    assert _display(block, {"heading": "Sponsor", "kind": "auto"}) == "sponsor"


def test_heading_block_clean_materializes_auto_icon():
    block = ShowNoteHeadingBlock()
    value = block.clean(
        block.to_python({"heading": "Black Friday Sale", "kind": "auto", "icon": ""})
    )
    assert value["kind"] == "auto"
    assert value["icon"] == "sale"


def test_clean_keeps_explicit_override_and_materializes_it():
    block = ShowNoteHeadingBlock()
    value = block.clean(
        block.to_python({"heading": "Black Friday Sale", "kind": "books", "icon": ""})
    )
    assert value["kind"] == "books"
    assert value["icon"] == "books"


def test_sponsor_block_clean_materializes_sponsor_icon():
    block = ShowNoteSponsorBlock()
    value = block.clean(
        block.to_python(
            {
                "heading": "Sponsor",
                "kind": "auto",
                "icon": "",
                "sponsor_name": "ACME",
                "sponsor_url": "https://acme.test",
                "copy": "",
                "coupon_code": "",
            }
        )
    )
    assert value["icon"] == "sponsor"


def test_heading_block_factory_name():
    assert heading_block()[0] == "show_note_heading"
