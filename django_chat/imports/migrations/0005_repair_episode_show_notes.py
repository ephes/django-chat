from django.db import migrations


def repair_existing_episode_show_notes(apps, schema_editor):
    Episode = apps.get_model("cast", "Episode")
    EpisodeSourceMetadata = apps.get_model("imports", "EpisodeSourceMetadata")

    from django_chat.imports.show_note_backfill import repair_imported_episode_show_notes

    repair_imported_episode_show_notes(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=True,
        collect_items=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("imports", "0004_normalize_episode_body_show_note_headings"),
    ]

    operations = [
        migrations.RunPython(
            repair_existing_episode_show_notes,
            migrations.RunPython.noop,
        ),
    ]
