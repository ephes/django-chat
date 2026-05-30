from __future__ import annotations

from wagtail import blocks

RICH_TEXT_FEATURES = ["bold", "italic", "link"]

LINK_LIST_KIND_CHOICES = [
    ("links", "Links"),
    ("projects", "Projects"),
    ("books", "Books"),
    ("youtube", "YouTube"),
    ("groups", "Groups"),
    ("shameless_plugs", "Shameless Plugs"),
    ("support", "Support the Show"),
    ("sponsors", "Sponsors"),
    ("sponsoring_options", "Sponsoring Options"),
    ("other", "Other"),
]


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


class ShowNoteSponsorBlock(blocks.StructBlock):
    heading = blocks.CharBlock(default="Sponsor")
    sponsor_name = blocks.CharBlock()
    sponsor_url = blocks.URLBlock()
    copy = blocks.RichTextBlock(features=RICH_TEXT_FEATURES, required=False)
    coupon_code = blocks.CharBlock(required=False)

    class Meta:
        icon = "tag"
        label = "Show-note sponsor"
        template = "cast/django_chat/show_notes/sponsor.html"


class ShowNoteLinkListBlock(blocks.StructBlock):
    heading = blocks.CharBlock(default="Links")
    kind = blocks.ChoiceBlock(choices=LINK_LIST_KIND_CHOICES, default="links")
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
