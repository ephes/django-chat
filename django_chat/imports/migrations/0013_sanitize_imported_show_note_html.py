from django.db import migrations


def sanitize_imported_show_note_html(apps, schema_editor):
    Episode = apps.get_model("cast", "Episode")
    EpisodeSourceMetadata = apps.get_model("imports", "EpisodeSourceMetadata")

    from django_chat.imports.show_note_backfill import sanitize_imported_episode_bodies

    sanitize_imported_episode_bodies(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("imports", "0012_strip_markdown_hashes_from_show_note_headings"),
    ]

    operations = [
        migrations.RunPython(
            sanitize_imported_show_note_html,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
