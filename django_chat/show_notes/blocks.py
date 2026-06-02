from __future__ import annotations

from django import forms
from wagtail import blocks

from django_chat.imports.show_notes import display_icon, materialize_icon
from django_chat.show_notes.icons import kind_choices
from django_chat.show_notes.widgets import IconChoiceWidget

RICH_TEXT_FEATURES = ["bold", "italic", "link"]


def _kind_block() -> blocks.ChoiceBlock:
    """Editor intent: "auto" (default) or an explicit icon override."""
    return blocks.ChoiceBlock(choices=kind_choices(), default="auto", widget=IconChoiceWidget())


def _icon_block() -> blocks.CharBlock:
    """Materialized concrete icon kind, set by the system; hidden in the admin."""
    return blocks.CharBlock(required=False, default="", widget=forms.HiddenInput)


class IconBlockMixin:
    """Materialize the concrete ``icon`` on save/preview (``clean``) and expose a
    render-time ``display_kind`` that falls back to deriving from the heading when
    ``icon`` has not been materialized yet (old revisions / un-migrated JSON)."""

    def clean(self, value):  # type: ignore[no-untyped-def]
        value = super().clean(value)  # ty: ignore[unresolved-attribute]
        value["icon"] = materialize_icon(value)
        return value

    def get_context(self, value, parent_context=None):  # type: ignore[no-untyped-def]
        context = super().get_context(value, parent_context)  # ty: ignore[unresolved-attribute]
        context["display_kind"] = display_icon(value)
        return context


class ShowNoteExtraLinkBlock(blocks.StructBlock):
    title = blocks.CharBlock()
    url = blocks.URLBlock()

    class Meta:
        icon = "link"
        label = "Extra link"
        label_format = "{title}"


class ShowNoteLinkItemBlock(blocks.StructBlock):
    title = blocks.CharBlock()
    url = blocks.URLBlock()
    description = blocks.RichTextBlock(features=RICH_TEXT_FEATURES, required=False)
    extra_links = blocks.ListBlock(ShowNoteExtraLinkBlock(), required=False)

    class Meta:
        icon = "link"
        label = "Link item"
        label_format = "{title}"


class ShowNoteHeadingBlock(IconBlockMixin, blocks.StructBlock):
    heading = blocks.CharBlock()
    kind = _kind_block()
    icon = _icon_block()

    class Meta:
        icon = "title"
        label = "Show-note heading"
        template = "cast/django_chat/show_notes/heading.html"


class ShowNoteSponsorBlock(IconBlockMixin, blocks.StructBlock):
    heading = blocks.CharBlock(default="Sponsor")
    kind = _kind_block()
    icon = _icon_block()
    sponsor_name = blocks.CharBlock()
    sponsor_url = blocks.URLBlock()
    copy = blocks.RichTextBlock(features=RICH_TEXT_FEATURES, required=False)
    coupon_code = blocks.CharBlock(required=False)

    class Meta:
        icon = "tag"
        label = "Show-note sponsor"
        template = "cast/django_chat/show_notes/sponsor.html"


class ShowNoteLinkListBlock(IconBlockMixin, blocks.StructBlock):
    heading = blocks.CharBlock(default="Links")
    show_heading = blocks.BooleanBlock(default=True, required=False)
    show_items = blocks.BooleanBlock(default=True, required=False)
    kind = _kind_block()
    icon = _icon_block()
    intro = blocks.RichTextBlock(features=RICH_TEXT_FEATURES, required=False)
    items = blocks.ListBlock(ShowNoteLinkItemBlock(), min_num=1)

    class Meta:
        icon = "link"
        label = "Show-note link list"
        template = "cast/django_chat/show_notes/link_list.html"


def sponsor_block() -> tuple[str, blocks.Block]:
    return "show_note_sponsor", ShowNoteSponsorBlock()


def link_list_block() -> tuple[str, blocks.Block]:
    return "show_note_link_list", ShowNoteLinkListBlock()


def heading_block() -> tuple[str, blocks.Block]:
    return "show_note_heading", ShowNoteHeadingBlock()
