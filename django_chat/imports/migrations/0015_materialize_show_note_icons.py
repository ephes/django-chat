"""Forward-materialize show-note icons on existing episode bodies.

This walks every saved ``cast.Episode`` body and, for each structured show-note
block, sets the concrete ``icon`` field and normalises the ``kind`` field to the
new auto/override model:

* ``icon`` is derived from the block's intent (an explicit override wins, else it
  is resolved from the heading), so rendering no longer has to resolve at display
  time.
* System-derived ``kind`` values (the ones the importer produced, plus the
  deprecated ``other``) are reset to ``"auto"`` so the admin shows "Automatisch"
  and future heading edits re-derive the icon. Genuine editor overrides
  (a stored ``kind`` that differs from what the heading would auto-resolve to)
  are preserved.

This is deliberately icon-only: it never re-parses or sanitizes stored HTML, so
authored RichText markup (``linktype``/``id`` etc.) is left untouched. It is
idempotent and forward-only.
"""

from django.db import migrations

SHOW_NOTE_BLOCK_TYPES = {
    "show_note_link_list",
    "show_note_sponsor",
    "show_note_heading",
}
# kind values that are never genuine editor overrides and should normalise to auto
_SYSTEM_KINDS = {"auto", "other", ""}


def _materialize_block_value(value, resolve_icon_kind) -> bool:
    if not isinstance(value, dict):
        return False
    heading = value.get("heading") or ""
    old_kind = value.get("kind") or "auto"
    derived = resolve_icon_kind(heading)
    if old_kind in _SYSTEM_KINDS or old_kind == derived:
        new_kind = "auto"
        icon = derived
    else:
        # A stored kind that diverges from the auto result is a real override.
        new_kind = old_kind
        icon = old_kind
    changed = value.get("kind") != new_kind or value.get("icon") != icon
    value["kind"] = new_kind
    value["icon"] = icon
    return changed


def materialize_show_note_icons(apps, schema_editor):
    Episode = apps.get_model("cast", "Episode")
    from django_chat.imports.show_notes import resolve_icon_kind

    for episode in Episode.objects.all().iterator(chunk_size=100):
        body = episode.body
        body_value = body.get_prep_value() if hasattr(body, "get_prep_value") else body
        if not isinstance(body_value, list):
            continue
        changed = False
        for section in body_value:
            if not isinstance(section, dict) or not isinstance(section.get("value"), list):
                continue
            for child in section["value"]:
                if isinstance(child, dict) and child.get("type") in SHOW_NOTE_BLOCK_TYPES:
                    if _materialize_block_value(child.get("value"), resolve_icon_kind):
                        changed = True
        if changed:
            Episode.objects.filter(pk=episode.pk).update(body=body_value)


class Migration(migrations.Migration):
    dependencies = [
        ("imports", "0014_drop_unsafe_imported_source_links"),
    ]

    operations = [
        migrations.RunPython(
            materialize_show_note_icons,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
