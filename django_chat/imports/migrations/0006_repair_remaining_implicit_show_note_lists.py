from django.db import migrations


def repair_remaining_implicit_show_note_lists(apps, schema_editor):
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
        ("imports", "0005_repair_episode_show_notes"),
    ]

    operations = [
        migrations.RunPython(
            repair_remaining_implicit_show_note_lists,
            migrations.RunPython.noop,
        ),
    ]
