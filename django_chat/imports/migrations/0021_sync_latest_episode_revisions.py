"""Re-apply earlier live-row repairs to each episode's latest Wagtail revision.

Migrations 0004–0020 and the repair commands wrote only the live
``cast.Episode`` row. Wagtail's editor loads the latest revision, so the next
*Publish* of an affected episode would have reverted those repairs (including
the 0013 HTML sanitization and the 0020 comments default).

For published episodes without a pending draft, the latest revision is aligned
with the live row (body, search description, comments flag), so republishing
changes nothing. Pending drafts are never published: they receive the
idempotent, editor-safe body repairs in place (unsafe markup removed while
Wagtail links/embeds are kept; icons materialized only where none is stored;
the implicit-list un-hide from 0018) and are printed as divergent drafts for
editor review (the same report is available any time via
``manage.py sync_django_chat_episode_revisions``).

Idempotent and forward-only; it never touches live rows or publish state.
"""

from django.db import migrations


def sync_latest_episode_revisions(apps, schema_editor):
    Episode = apps.get_model("cast", "Episode")
    EpisodeSourceMetadata = apps.get_model("imports", "EpisodeSourceMetadata")

    from django_chat.imports.management.commands.sync_django_chat_episode_revisions import (
        format_revision_sync_report,
    )
    from django_chat.imports.revision_sync import sync_episode_revisions

    result = sync_episode_revisions(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=True,
    )
    if result.revisions_synced or result.divergent_drafts:
        for line in format_revision_sync_report(result, write=True):
            print(f"  imports.0021: {line}")


class Migration(migrations.Migration):
    dependencies = [
        ("imports", "0020_enable_comments_on_imported_episodes"),
        ("wagtailcore", "0073_page_latest_revision"),
    ]

    operations = [
        migrations.RunPython(
            sync_latest_episode_revisions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
