"""Wagtail page model for the editorial Sponsor Us subpage.

The page replaces the upstream Simplecast "Sponsor Us" link (a Google Doc) with
an editable on-site page that also offers the original document as a PDF
download. It lives under the Wagtail home page (the site's root_page) to keep
it decoupled from django-cast's Podcast/Episode subpage_types. Routing in
``config/urls.py`` exposes it at ``/episodes/sponsor/`` so the URL parallels
the existing ``/episodes/feed/`` subscribe page.
"""

from __future__ import annotations

from typing import Any, ClassVar, cast

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page


class SponsorPage(Page):
    """Singleton subpage explaining sponsorship opportunities."""

    eyebrow = models.CharField(max_length=80, default="Sponsorship")
    heading = models.CharField(max_length=160, default="Sponsor Django Chat")
    tagline = models.TextField(blank=True)
    stats_intro = RichTextField(blank=True)
    hosts_bio = RichTextField(blank=True)
    cta_email = models.EmailField(default="will@wsvincent.com")
    pricing_note = models.CharField(
        max_length=255,
        blank=True,
        default=(
            "There is only one sponsor per episode who receives mention in the "
            "pre-roll, mid-roll, and out-roll along with prominent placement in "
            "the show notes."
        ),
    )
    reviews_intro = models.CharField(
        max_length=255,
        blank=True,
        default=(
            "We have a near-perfect 4.9 star rating. Check out our ratings and "
            "more reviews at Chartable."
        ),
    )
    pdf = models.ForeignKey(
        "wagtaildocs.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    parent_page_types: ClassVar[list[str]] = ["wagtailcore.Page"]
    subpage_types: ClassVar[list[str]] = []
    max_count = 1

    content_panels = [
        *Page.content_panels,
        MultiFieldPanel(
            [
                FieldPanel("eyebrow"),
                FieldPanel("heading"),
                FieldPanel("tagline"),
            ],
            heading="Header",
        ),
        InlinePanel("slots", label="Sponsorship slot", min_num=0, max_num=8),
        FieldPanel("stats_intro"),
        InlinePanel("stats", label="Traffic stat", min_num=0, max_num=8),
        FieldPanel("hosts_bio"),
        InlinePanel("pricing_tiers", label="Pricing tier", min_num=0, max_num=6),
        FieldPanel("cta_email"),
        FieldPanel("pricing_note"),
        FieldPanel("reviews_intro"),
        InlinePanel("reviews", label="Review", min_num=0, max_num=12),
        FieldPanel("pdf"),
    ]

    template = "cast/django_chat/sponsor.html"

    def get_context(self, request: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context(request, *args, **kwargs)
        self_any = cast(Any, self)
        context["slots"] = list(self_any.slots.all())
        context["stats"] = list(self_any.stats.all())
        context["pricing_tiers"] = list(self_any.pricing_tiers.all())
        context["reviews"] = list(self_any.reviews.all())
        return context


class SponsorSlot(Orderable):
    """A single sponsorship slot (Pre-roll / Mid-roll / Out-roll / Show Notes)."""

    page = ParentalKey(SponsorPage, on_delete=models.CASCADE, related_name="slots")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255)

    panels: ClassVar[list[Any]] = [
        FieldPanel("name"),
        FieldPanel("description"),
    ]


class SponsorStat(Orderable):
    """A single traffic number (e.g. "180+" / "episodes")."""

    page = ParentalKey(SponsorPage, on_delete=models.CASCADE, related_name="stats")
    value = models.CharField(max_length=40)
    label = models.CharField(max_length=120)

    panels: ClassVar[list[Any]] = [
        FieldPanel("value"),
        FieldPanel("label"),
    ]


class SponsorPricingTier(Orderable):
    """A single pricing tier (e.g. "Single Episode $250")."""

    page = ParentalKey(SponsorPage, on_delete=models.CASCADE, related_name="pricing_tiers")
    name = models.CharField(max_length=80)
    price = models.CharField(max_length=40)
    description = models.CharField(max_length=160, blank=True)

    panels: ClassVar[list[Any]] = [
        FieldPanel("name"),
        FieldPanel("price"),
        FieldPanel("description"),
    ]


class SponsorReview(Orderable):
    """A single listener review with full text."""

    page = ParentalKey(SponsorPage, on_delete=models.CASCADE, related_name="reviews")
    title = models.CharField(max_length=160)
    body = models.TextField()
    stars = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )

    panels: ClassVar[list[Any]] = [
        FieldPanel("title"),
        FieldPanel("body"),
        FieldPanel("stars"),
    ]
