from __future__ import annotations

import pytest

from django_chat.core.templatetags.dc_filters import duration_minutes


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (4663, "78 MIN"),
        (60, "1 MIN"),
        (29, "0 MIN"),
        (None, ""),
        (0, ""),
    ],
)
def test_duration_minutes_formats_or_returns_empty(seconds, expected):
    assert duration_minutes(seconds) == expected
