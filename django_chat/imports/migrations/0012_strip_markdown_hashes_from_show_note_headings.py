from django.db import migrations


def strip_markdown_hashes_from_show_note_headings(apps, schema_editor):
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
        ("imports", "0011_restore_support_boilerplate_copy"),
    ]

    operations = [
        migrations.RunPython(
            strip_markdown_hashes_from_show_note_headings,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
