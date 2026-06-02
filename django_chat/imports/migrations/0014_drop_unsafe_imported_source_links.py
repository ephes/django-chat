from django.db import migrations


def drop_unsafe_imported_source_links(apps, schema_editor):
    PodcastSourceLink = apps.get_model("imports", "PodcastSourceLink")

    from django_chat.imports.show_note_backfill import drop_unsafe_source_links

    drop_unsafe_source_links(PodcastSourceLink=PodcastSourceLink, write=True)


class Migration(migrations.Migration):
    dependencies = [
        ("imports", "0013_sanitize_imported_show_note_html"),
    ]

    operations = [
        migrations.RunPython(
            drop_unsafe_imported_source_links,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
