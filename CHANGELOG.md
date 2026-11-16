# Changelog

## Unreleased

- Unwind newly saved cover objects when catalog metadata or commit fails;
  require an outermost transaction for imports with artwork and retain existing
  covers. Admit covers before persistence under 20 MiB, 16 million pixels, and
  a single-frame limit.
- Refuse conflicting episode matching keys, GUIDs, IDs, and slug fallbacks.
  Deduplicate Simplecast detail/list copies by ID and require one-to-one,
  unambiguous RSS matches, with detail payload precedence.
- Serialize PostgreSQL first-import tree writes on the existing parent page,
  reloading its state after locking and fetching covers before the reservation.
- Bound regular fixture reads to 16 MiB, JSON depth to 64, and JSON structural
  punctuation to 200,000 tokens; refuse special files, symlinks, and duplicate
  JSON members before import effects.
