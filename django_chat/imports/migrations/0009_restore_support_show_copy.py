from django.db import migrations


def restore_support_show_copy(apps, schema_editor):
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
        ("imports", "0008_convert_legacy_markdown_show_notes"),
    ]

    operations = [
        migrations.RunPython(
            restore_support_show_copy,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
