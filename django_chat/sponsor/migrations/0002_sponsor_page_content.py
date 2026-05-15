"""Data migration: create the singleton SponsorPage under the Wagtail home page.

Populates the page with the verbatim text of the original Google-Doc one-pager
(see ``/tmp/sponsor_clean.txt`` in the brief) and attaches the checked-in PDF
as a ``wagtaildocs.Document`` so it remains downloadable through Wagtail's
document delivery view even if the static file path ever moves.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import migrations


SLOTS: tuple[tuple[str, str], ...] = (
    ("Pre-roll", "Kick off the episode with your brand's mention"),
    ("Mid-roll", "A dedicated 1-minute spotlight for your message"),
    ("Out-roll", "A closing 10-second note at the end"),
    ("Show Notes", "Prominent listing in the episode's show notes"),
)

STATS: tuple[tuple[str, str], ...] = (
    ("180+", "biweekly episodes<br>(pause over summer)"),
    ("700,000+", "downloads<br>to date"),
    ("2,000", "downloads on average<br>in the first week"),
    ("4.9", "near-perfect<br>star rating"),
)

PRICING: tuple[tuple[str, str, str], ...] = (
    ("Single Episode", "$250", ""),
    ("Five Episode Package", "$1,000", "20% discount"),
)

REVIEWS: tuple[tuple[str, str], ...] = (
    (
        "Important podcast in this space",
        (
            "As a professional Django developer, I am so glad this podcast "
            "exists. Django is a great framework with a rich ecosystem and "
            "it's used by some of the biggest and most important companies in "
            "the world. It's only fitting that the hosts, a Django educator "
            "and Django fellow, would be the ones to bring us the ideas, "
            "people, and news important to those of us in this space. The "
            "podcast is informative and entertaining!"
        ),
    ),
    (
        "Everything interesting in Django",
        "One of the few podcasts I make a point of not missing!",
    ),
    (
        "So amazing!!",
        (
            "I have been trying to learn how to make a website with Django "
            "and this podcast has been entertaining and helpful."
        ),
    ),
    (
        "Informative, engaging, and insightful",
        (
            "Will and Carlton, along with their incredibly knowledgeable "
            "guests, deliver nothing but value in each and every episode."
        ),
    ),
    (
        "Fantastic",
        (
            "I'm an iOS dev trying to cobble together my own DRF backend and "
            "this podcast has been vital to me. It's so helpful to hear about "
            "these topics in a conversational format."
        ),
    ),
)

STATS_INTRO_HTML = (
    "<p>We are the #1 Django podcast by audience and rank as the first "
    "search result for Django Podcast on Google, Bing, and DuckDuckGo. "
    "(Traffic as of October 2024)</p>"
)

HOSTS_BIO_HTML = (
    "<p>The podcast was started in February by Will Vincent and Carlton "
    "Gibson. Will is the author of several books on Django, co-writes the "
    "Django News newsletter, and is a former Board Member of the Django "
    "Software Foundation. Carlton served as a Django Fellow for five years "
    "and maintains a number of key packages in the Django ecosystem "
    "including Django REST Framework, Django Filter, Django Crispy Forms, "
    "Channels/Daphne/Channel Redis, and many more.</p>"
)

PDF_RELATIVE_PATH = "django_chat/files/django-chat-sponsorship-kit.pdf"


def create_sponsor_page(apps, schema_editor):
    Site = apps.get_model("wagtailcore", "Site")
    SponsorPage = apps.get_model("sponsor", "SponsorPage")
    SponsorSlot = apps.get_model("sponsor", "SponsorSlot")
    SponsorStat = apps.get_model("sponsor", "SponsorStat")
    SponsorPricingTier = apps.get_model("sponsor", "SponsorPricingTier")
    SponsorReview = apps.get_model("sponsor", "SponsorReview")
    Document = apps.get_model("wagtaildocs", "Document")
    ContentType = apps.get_model("contenttypes", "ContentType")

    if SponsorPage.objects.exists():
        return

    default_site = Site.objects.filter(is_default_site=True).first()
    if default_site is None:
        # Fresh database before any Site row exists: do nothing; the page can
        # be created via the admin or a follow-up command once the site is up.
        return
    parent_page = default_site.root_page

    sponsor_content_type, _ = ContentType.objects.get_or_create(
        app_label="sponsor",
        model="sponsorpage",
    )

    # Wagtail Page insertion needs treebeard MP_Node helpers which are only
    # available on the concrete models, not on historical (`apps.get_model`)
    # ones. Importing the concrete classes here is the standard Wagtail data
    # migration pattern for seed pages.
    from wagtail.models import Page as ConcretePage  # noqa: PLC0415

    from django_chat.sponsor.models import SponsorPage as ConcreteSponsorPage  # noqa: PLC0415

    concrete_parent = ConcretePage.objects.get(pk=parent_page.pk)
    concrete_page = ConcreteSponsorPage(
        title="Sponsor Us",
        slug="sponsor",
        eyebrow="Sponsorship",
        heading="Sponsor Django Chat",
        tagline=(
            "Join us as the exclusive sponsor of one or more episodes and "
            "connect with a vibrant and dedicated community of Django "
            "developers."
        ),
        stats_intro=STATS_INTRO_HTML,
        hosts_bio=HOSTS_BIO_HTML,
        cta_email="will@wsvincent.com",
        pricing_note=(
            "There is only one sponsor per episode who receives mention in the "
            "pre-roll, mid-roll, and out-roll along with prominent placement "
            "in the show notes."
        ),
        reviews_intro=(
            "We have a near-perfect 4.9 star rating. Check out our ratings and "
            "more reviews at Chartable."
        ),
    )
    concrete_parent.add_child(instance=concrete_page)

    # Attach the bundled one-pager as a Wagtail Document (historical model is
    # fine here because we only set the file/title fields).
    pdf_source = Path(settings.APPS_DIR) / "static" / PDF_RELATIVE_PATH
    if pdf_source.exists():
        with pdf_source.open("rb") as handle:
            document = Document.objects.create(
                title="Django Chat sponsorship one-pager",
            )
            document.file.save(
                "django-chat-sponsorship-kit.pdf",
                File(handle),
                save=True,
            )
        # Update via the historical model so the FK column is set without
        # triggering page save signals again.
        SponsorPage.objects.filter(pk=concrete_page.pk).update(pdf_id=document.pk)

    # Populate inline children via the historical models.
    page_row = SponsorPage.objects.get(pk=concrete_page.pk)
    for order, (name, description) in enumerate(SLOTS):
        SponsorSlot.objects.create(
            page=page_row, sort_order=order, name=name, description=description
        )
    for order, (value, label) in enumerate(STATS):
        SponsorStat.objects.create(
            page=page_row, sort_order=order, value=value, label=label
        )
    for order, (name, price, description) in enumerate(PRICING):
        SponsorPricingTier.objects.create(
            page=page_row,
            sort_order=order,
            name=name,
            price=price,
            description=description,
        )
    for order, (title, body) in enumerate(REVIEWS):
        SponsorReview.objects.create(
            page=page_row,
            sort_order=order,
            title=title,
            body=body,
            stars=5,
        )


def remove_sponsor_page(apps, schema_editor):
    SponsorPage = apps.get_model("sponsor", "SponsorPage")
    # Use the historical page row to drop children; treebeard ops are not
    # available here so we leave any orphan tree state cleanup to a full
    # database rebuild — acceptable for a singleton editorial page.
    SponsorPage.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sponsor", "0001_initial"),
        ("wagtailcore", "0097_baselogentry_uuid_action_timestamp_indexes"),
        ("wagtaildocs", "0014_alter_document_file_size"),
    ]

    operations = [
        migrations.RunPython(create_sponsor_page, remove_sponsor_page),
    ]
