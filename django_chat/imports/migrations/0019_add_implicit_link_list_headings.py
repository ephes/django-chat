"""Add iconed "Links" headings to headingless implicit link lists (D5).

A leading source list with no heading whose items cannot be cleanly itemized
(prose mixed with links, multiple anchors per item, …) was left as a raw ``<ul>``
inside a ``paragraph`` block: no heading, no icon. The clean-list path already
converts fully-itemizable leading lists into ``show_note_link_list`` blocks, and
``0017`` offloaded *headed* non-convertible sections into iconed
``show_note_heading`` blocks — but a *headingless* non-convertible leading list
fell through both and rendered bare, contrary to the icon model ("every link
section carries an iconed heading").

This re-runs the in-place show-note structuring over imported episode bodies,
which now synthesizes an iconed "Links" ``show_note_heading`` before such a list
(keeping the list verbatim as a following paragraph). It deliberately re-uses the
same idempotent structuring as ``0017``: already-structured blocks are left
alone, a list that already follows its own stored heading does not gain a
spurious "Links" heading, and a link-less bullet list (no real anchors) is not
treated as a "Links" section. Idempotent and forward-only. Scoped to imported
episodes (those with ``EpisodeSourceMetadata``); manually authored bodies are
left untouched.
"""

from django.db import migrations


def add_implicit_link_list_headings(apps, schema_editor):
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
        ("imports", "0018_unhide_implicit_link_list_headings"),
    ]

    operations = [
        migrations.RunPython(
            add_implicit_link_list_headings,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
