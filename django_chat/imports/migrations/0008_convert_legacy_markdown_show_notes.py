from django.db import migrations


def convert_legacy_markdown_show_notes(apps, schema_editor):
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
        ("imports", "0007_hide_implicit_link_list_headings"),
    ]

    operations = [
        migrations.RunPython(
            convert_legacy_markdown_show_notes,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
