"""Offload raw show-note section headings into iconed heading blocks (D5).

Episodes structured before the D5 rule ("every real heading becomes an iconed
block", added with the icon feature) kept non-convertible sections — e.g. a
``📚 Books`` or ``SHAMELESS PLUGS`` list with prose around the links — as raw
``<h3>…</h3>`` HTML inside a ``paragraph`` block. Those headings rendered the
literal source text (emoji/caps) with no icon, and the icon migrations
(``0015``/``0016``) only touch already-structured blocks, so they never reached
them.

This re-runs the in-place show-note structuring over imported episode bodies,
which now offloads such headings into ``show_note_heading`` blocks (canonical
label text + materialised icon) and keeps the list as a following paragraph.

It is deliberately *not* a source-based repair: it only re-structures ``detail``
paragraph children and leaves already-structured blocks alone, so genuine icon
overrides set since the icon feature shipped are preserved. Idempotent and
forward-only. Scoped to imported episodes (those with ``EpisodeSourceMetadata``);
manually authored bodies are left untouched.
"""

from django.db import migrations


def offload_raw_show_note_headings(apps, schema_editor):
    Episode = apps.get_model("cast", "Episode")
    EpisodeSourceMetadata = apps.get_model("imports", "EpisodeSourceMetadata")

    from django_chat.imports.show_notes import structure_episode_body_show_notes

    for metadata in EpisodeSourceMetadata.objects.select_related("episode").iterator(
        chunk_size=100
    ):
        episode = metadata.episode
        if episode is None:
            continue
        new_body, changed = structure_episode_body_show_notes(episode.body)
        if changed:
            Episode.objects.filter(pk=episode.pk).update(body=new_body)


class Migration(migrations.Migration):
    dependencies = [
        ("imports", "0016_heal_show_note_icons"),
    ]

    operations = [
        migrations.RunPython(
            offload_raw_show_note_headings,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
