from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

from django_chat.core.sponsor_shoutout import wrap_sponsor_shoutout

register = template.Library()


@register.tag("sponsor_shoutout")
def sponsor_shoutout(parser, token):
    """Wrap show-notes markup; restyle its "Sponsor" section as a chat bubble.

    A byte-exact no-op for episodes without a sponsor section; otherwise only
    that section is restyled and the rest of the show notes renders identically
    (DOM-equivalent — see ``wrap_sponsor_shoutout``)."""
    nodelist = parser.parse(("endsponsor_shoutout",))
    parser.delete_first_token()
    return _SponsorShoutoutNode(nodelist)


class _SponsorShoutoutNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        return mark_safe(wrap_sponsor_shoutout(self.nodelist.render(context)))
