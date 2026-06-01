from django.db import migrations


def restore_source_detail_show_notes(apps, schema_editor):
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
        ("imports", "0009_restore_support_show_copy"),
    ]

    operations = [
        migrations.RunPython(
            restore_source_detail_show_notes,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
