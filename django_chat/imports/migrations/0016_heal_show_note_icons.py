"""Heal show-note icons frozen by the initially-shipped 0015.

0015 first shipped with a classifier that mistook the legacy
``ShowNoteLinkListBlock.kind="links"`` default for a deliberate editor override.
That froze the icon on every link-list section whose heading resolves to a
different kind — e.g. a "Books" heading left at the default kept the links icon
instead of materialising the books icon. 0015 has since been corrected to treat
that legacy default as a system value.

This migration re-runs the corrected backfill so environments that already
applied the buggy 0015 (staging) are healed. It reuses the corrected 0015 data
function, so it is forward-only and idempotent: genuine overrides (a stored kind
that is neither a system value nor the legacy link-list default) are preserved.
"""

from importlib import import_module

from django.db import migrations

_materialize = import_module("django_chat.imports.migrations.0015_materialize_show_note_icons")


class Migration(migrations.Migration):
    dependencies = [
        ("imports", "0015_materialize_show_note_icons"),
    ]

    operations = [
        migrations.RunPython(
            _materialize.materialize_show_note_icons,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
