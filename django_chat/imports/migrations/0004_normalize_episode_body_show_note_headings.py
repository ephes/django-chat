from django.db import migrations


def normalize_existing_episode_bodies(apps, schema_editor):
    Episode = apps.get_model("cast", "Episode")

    from django_chat.imports.show_notes import normalize_episode_body_show_notes

    for episode in Episode.objects.only("pk", "body").iterator(chunk_size=100):
        body, changed = normalize_episode_body_show_notes(episode.body)
        if changed:
            Episode.objects.filter(pk=episode.pk).update(body=body)


class Migration(migrations.Migration):
    dependencies = [
        # imports.0001 depends on cast.0062, where Episode.body is already present.
        ("imports", "0003_podcastsourcelink"),
    ]

    operations = [
        migrations.RunPython(
            normalize_existing_episode_bodies,
            migrations.RunPython.noop,
        ),
    ]
