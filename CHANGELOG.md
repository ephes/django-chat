# Changelog

## Unreleased

- Upgrade Wagtail 8.0.1 to 8.1 (range `>=8.1,<8.2`) and relock django-cast
  develop from `b594f805` to `e0c632ad` (release 0.2.68 plus the 0.2.69
  version bump), the revision homepage and python-podcast run.
  draftjs-exporter moves to 7.3.1 and soupsieve to 4.1.1 (django-cast's new
  floor). django-cast adds migrations `cast.0091` to `cast.0094`. The comment
  template override posts django-cast's comment revision token, which author
  edits now require. The sample and catalog importer records the copied
  file's name with its size, and `cache_django_chat_audio_sizes` binds the
  sizes of existing audio files. `just deploy-staging` checks for ops-control's
  `django_chat` service instead of the removed playbook.
- Unwind newly saved cover objects when catalog metadata or commit fails;
  require an outermost transaction for imports with artwork and retain existing
  covers. Admit covers before persistence under 20 MiB, 16 million pixels, and
  a single-frame limit.
- Refuse conflicting episode matching keys, GUIDs, IDs, and slug fallbacks.
  Deduplicate Simplecast detail/list copies by ID and require one-to-one,
  unambiguous RSS matches, with detail payload precedence. Refuse merged
  records that share one matching key (for example GUID-less RSS items with a
  repeated episode number), refuse a slug held by another podcast's episode,
  and update only the metadata row the identity check resolved.
- Keep a Simplecast GUID known from a list copy when the preferred detail copy
  of the same ID omits it, so the episode still matches its RSS item.
- Serialize PostgreSQL first-import tree writes on the existing parent page,
  reloading its state after locking and fetching covers before the reservation.
- Bound regular fixture reads to 16 MiB, JSON depth to 64, and JSON structural
  punctuation to 200,000 tokens; refuse special files, symlinks, and duplicate
  JSON members before import effects.
