from __future__ import annotations

from django.db.migrations.loader import MigrationLoader

SPONSOR_SEED_MIGRATION = ("sponsor", "0002_sponsor_page_content")
# The wagtailsearch migration the seed depends on. Do not move this to newer
# wagtailsearch migrations on Wagtail upgrades: databases that already applied
# the seed would then have an applied migration with an unapplied dependency,
# and Django refuses to migrate them (InconsistentMigrationHistory).
WAGTAILSEARCH_DEPENDENCY = ("wagtailsearch", "0010_add_text_fields")


def test_sponsor_seed_migration_runs_after_wagtailsearch() -> None:
    """The seed migration saves a concrete page, which Wagtail indexes at once.

    On an empty PostgreSQL database the INSERT into the missing
    ``wagtailsearch_indexentry`` table aborts the whole migration transaction,
    so the search index tables have to exist before the seed runs. SQLite
    tolerates the failed insert, so the in-memory test database alone does not
    catch a missing dependency; CI also migrates an empty PostgreSQL database.
    """
    graph = MigrationLoader(None, ignore_no_migrations=True).graph
    assert WAGTAILSEARCH_DEPENDENCY in graph.forwards_plan(SPONSOR_SEED_MIGRATION)
