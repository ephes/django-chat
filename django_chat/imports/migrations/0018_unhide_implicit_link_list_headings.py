"""Un-hide implicit link-list headings.

A leading source list with no heading was converted to a `show_note_link_list`
with `show_heading=False` (originally migration `0007_hide_implicit_link_list_headings`),
so it rendered as a bare list. Under the icon model that also hides the icon —
`link_list.html` skips the whole iconed `<h3>` when `show_heading` is False — so
~all episodes with a leading link list showed no marker at all. The icon model
wants every section to carry its iconed heading, so this reverses 0007: it drops
the `show_heading=False` flag on stored link-list blocks (reverting to the default
True), letting the already-materialised "Links" heading + icon render.

Touches only the `show_heading` flag — heading/kind/icon/items are left intact, so
genuine icon overrides are preserved. Narrowly scoped to the generated implicit
list (a `detail` `show_note_link_list` with the importer's `heading="Links"` and a
hidden heading), so a deliberately-hidden non-implicit (custom-heading) list keeps
its `show_heading=False`. Restricted to imported episodes (those with
`EpisodeSourceMetadata`); forward-only and idempotent.
"""

from django.db import migrations

SHOW_NOTE_LINK_LIST = "show_note_link_list"


def unhide_implicit_link_list_headings(apps, schema_editor):
    Episode = apps.get_model("cast", "Episode")
    EpisodeSourceMetadata = apps.get_model("imports", "EpisodeSourceMetadata")

    for metadata in EpisodeSourceMetadata.objects.select_related("episode").iterator(
        chunk_size=100
    ):
        episode = metadata.episode
        if episode is None:
            continue
        body = episode.body
        body_value = body.get_prep_value() if hasattr(body, "get_prep_value") else body
        if not isinstance(body_value, list):
            continue
        changed = False
        for section in body_value:
            if (
                not isinstance(section, dict)
                or section.get("type") != "detail"
                or not isinstance(section.get("value"), list)
            ):
                continue
            for child in section["value"]:
                # Only the generated implicit list — a detail show_note_link_list
                # with the importer's "Links" heading and a hidden heading — is
                # un-hidden. A deliberately-hidden non-implicit (custom-heading)
                # list keeps its show_heading=False.
                if (
                    isinstance(child, dict)
                    and child.get("type") == SHOW_NOTE_LINK_LIST
                    and isinstance(child.get("value"), dict)
                    and child["value"].get("show_heading") is False
                    and child["value"].get("heading") == "Links"
                ):
                    del child["value"]["show_heading"]
                    changed = True
        if changed:
            Episode.objects.filter(pk=episode.pk).update(body=body_value)


class Migration(migrations.Migration):
    dependencies = [
        ("imports", "0017_offload_raw_show_note_headings"),
    ]

    operations = [
        migrations.RunPython(
            unhide_implicit_link_list_headings,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
