"""Cache backends for the failed-login counters (docs/admin-login-throttle.md)."""

from __future__ import annotations

from django.core.cache.backends.filebased import FileBasedCache


class ExpiringFileBasedCache(FileBasedCache):
    """A ``FileBasedCache`` that drops expired entries before it culls.

    ``FileBasedCache`` removes an expired file only when its key is read again.
    Once ``MAX_ENTRIES`` is reached it deletes a random share of *all* files,
    live ones included. For the login counters every distinct username or
    client address leaves a file behind, so junk entries from earlier hours
    would eventually cull a live lockout. This backend first deletes every
    expired file and culls at random only if the live entries alone still
    reach the limit.
    """

    def _cull(self) -> None:
        filelist = self._list_cache_files()
        if len(filelist) < self._max_entries:
            return
        for fname in filelist:
            try:
                with open(fname, "rb") as handle:
                    self._is_expired(handle)
            except FileNotFoundError:
                continue
        super()._cull()
