"""Enable comments by default on imported episodes.

The podcast/blog page remains the main Wagtail switch for comments. Imported
episodes should be enabled by default so the podcast switch can activate the
catalog at once; individual episodes remain opt-out through their own
``comments_enabled`` flag.

Forward-only: after Wagtail editors change per-episode comment toggles, the
migration cannot distinguish rows it changed from deliberate admin choices.
"""

from django.db import migrations


def enable_comments_on_imported_episodes(apps, schema_editor):
    Episode = apps.get_model("cast", "Episode")
    EpisodeSourceMetadata = apps.get_model("imports", "EpisodeSourceMetadata")

    imported_episode_ids = EpisodeSourceMetadata.objects.exclude(episode_id=None).values_list(
        "episode_id",
        flat=True,
    )
    Episode.objects.filter(pk__in=imported_episode_ids, comments_enabled=False).update(
        comments_enabled=True
    )


class Migration(migrations.Migration):
    dependencies = [
        ("imports", "0019_add_implicit_link_list_headings"),
    ]

    operations = [
        migrations.RunPython(
            enable_comments_on_imported_episodes,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
