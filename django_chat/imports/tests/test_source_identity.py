from dataclasses import replace

import pytest

from django_chat.imports.import_sample import load_sample_source_data
from django_chat.imports.source_data import merge_episode_sources


def sources():
    source = next(
        episode
        for episode in load_sample_source_data().episodes
        if episode.rss and episode.simplecast
    )
    assert source.rss is not None and source.simplecast is not None
    return source.rss, source.simplecast


def test_unmatched_detail_and_list_deduplicate_by_id_with_first_precedence():
    _, detail = sources()
    listing = replace(detail, title="List summary", source_kind="list")
    merged = merge_episode_sources((), (detail, listing))
    assert len(merged) == 1
    assert merged[0].simplecast == detail
    assert merge_episode_sources((), (listing, detail))[0].simplecast == detail


@pytest.mark.parametrize("case", ["number", "reuse", "guid", "copies"])
def test_ambiguous_cross_source_identities_refuse(case):
    rss, detail = sources()
    if case == "number":
        rsses = (replace(rss, guid=""),)
        details = (replace(detail, guid=None), replace(detail, id="other-id", guid=None))
    elif case == "reuse":
        rsses = (replace(rss, guid=""), replace(rss, guid="", title="Another season"))
        details = (replace(detail, guid=None),)
    elif case == "guid":
        rsses = (rss,)
        details = (replace(detail, guid="conflicting-guid"),)
    else:
        rsses = ()
        details = (detail, replace(detail, guid="conflicting-guid"))
    with pytest.raises(ValueError, match="identity"):
        merge_episode_sources(rsses, details)


@pytest.mark.parametrize("case", ["repeated-guid", "three-copies"])
def test_unmatched_guid_ambiguity_refuses(case):
    _, detail = sources()
    details = (
        (detail, replace(detail, id="another-id"))
        if case == "repeated-guid"
        else (
            replace(detail, source_kind="list"),
            replace(detail, guid=None),
            replace(detail, guid="conflicting-guid", source_kind="list"),
        )
    )
    with pytest.raises(ValueError, match="identity"):
        merge_episode_sources((), details)


def test_unmatched_episodes_without_guids_keep_distinct_identities():
    _, detail = sources()
    first = replace(detail, guid=None)
    second = replace(detail, guid=None, id="other-season", season_number=2)
    merged = merge_episode_sources((), (first, second))
    assert len(merged) == 2
    assert len({episode.matching_key for episode in merged}) == 2


def test_rss_only_episodes_with_repeated_weak_key_refuse():
    rss, _ = sources()
    first = replace(rss, guid="")
    second = replace(rss, guid="", title="Same number, another season")
    with pytest.raises(ValueError, match="identity"):
        merge_episode_sources((first, second), ())
