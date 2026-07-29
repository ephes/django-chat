from __future__ import annotations

import gzip
import json
from io import StringIO
from pathlib import Path

import pytest
from cast.models.moderation import SpamFilter
from django.core.management import call_command
from django.core.management.base import CommandError

from django_chat.core.spamfilter import (
    extract_comment_corpus,
    label_counts,
    load_english_ham,
    model_to_json,
    stratified_split,
    train_model,
)
from django_chat.core.spamfilter.corpus import CorpusError

# ty cannot see the implicit manager on cast's SpamFilter model.
spam_filters = SpamFilter.objects  # ty: ignore[unresolved-attribute]

DUMP_TEMPLATE = """\
--
-- Some unrelated preamble
--
COPY public.wagtailcore_page (id, title) FROM stdin;
1\tHome
\\.

COPY public.django_comments (id, object_pk, user_name, user_email, user_url, comment, \
submit_date, ip_address, is_public, is_removed, content_type_id, site_id, user_id) FROM stdin;
1\t5\tAnna\tanna@example.com\t\\N\tGreat episode about Django\t2026-01-01\t\\N\tt\tf\t1\t1\t\\N
2\t5\tBot\tbot@spam.biz\t\\N\tCheap watches buy now\t2026-01-02\t\\N\tf\tt\t1\t1\t\\N
3\t5\tDeleted\tgone@example.com\t\\N\tRemoved by author\t2026-01-03\t\\N\tt\tf\t1\t1\t\\N
4\t5\tMulti\tm@example.com\t\\N\tLine one\\nline two\\tafter tab\t2026-01-04\t\\N\tt\tf\t1\t1\t\\N
\\.

COPY public.threadedcomments_comment (comment_ptr_id, title, tree_path, last_child_id, \
parent_id, newest_activity) FROM stdin;
1\tNice one\t0001\t\\N\t\\N\t2026-01-01
2\t\t0002\t\\N\t\\N\t2026-01-02
3\t\t0003\t\\N\t\\N\t2026-01-03
4\t\t0004\t\\N\t\\N\t2026-01-04
\\.

COPY public.cast_comments_commentauthormeta (id, comment_pk, edited, deleted_at) FROM stdin;
1\t3\tf\t2026-01-04
2\t1\tt\t\\N
\\.
"""


def write_dump(tmp_path: Path, *, gzipped: bool = False) -> Path:
    if gzipped:
        path = tmp_path / "dump.sql.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(DUMP_TEMPLATE)
        return path
    path = tmp_path / "dump.sql"
    path.write_text(DUMP_TEMPLATE, encoding="utf-8")
    return path


def test_extract_comment_corpus_labels_and_joins_title(tmp_path: Path) -> None:
    corpus = extract_comment_corpus(write_dump(tmp_path))

    # Comment 3 is author-deleted and must be excluded entirely.
    assert len(corpus) == 3
    assert label_counts(corpus) == {"ham": 2, "spam": 1}

    ham_messages = [message for label, message in corpus if label == "ham"]
    # message shape is "{name} {email} {title} {comment}"
    assert "Anna anna@example.com Nice one Great episode about Django" in ham_messages
    assert all("Removed by author" not in message for _label, message in corpus)


def test_extract_comment_corpus_decodes_escapes(tmp_path: Path) -> None:
    corpus = extract_comment_corpus(write_dump(tmp_path))
    multi = next(message for _label, message in corpus if "Line one" in message)

    assert "Line one\nline two\tafter tab" in multi


def test_extract_comment_corpus_reads_gzip(tmp_path: Path) -> None:
    assert extract_comment_corpus(write_dump(tmp_path, gzipped=True)) == extract_comment_corpus(
        write_dump(tmp_path)
    )


def test_extract_comment_corpus_rejects_dump_without_comments(tmp_path: Path) -> None:
    path = tmp_path / "empty.sql"
    path.write_text("COPY public.wagtailcore_page (id) FROM stdin;\n1\n\\.\n", encoding="utf-8")

    with pytest.raises(CorpusError, match="missing required table"):
        extract_comment_corpus(path)


def test_stratified_split_keeps_rare_label_in_both_halves() -> None:
    corpus = [("spam", f"spam {index}") for index in range(100)]
    corpus += [("ham", f"ham {index}") for index in range(10)]

    train, test = stratified_split(corpus, test_fraction=0.2, seed=1)

    assert sum(1 for label, _ in train if label == "ham") == 8
    assert sum(1 for label, _ in test if label == "ham") == 2
    assert sum(1 for label, _ in test if label == "spam") == 20


def test_stratified_split_is_deterministic_for_a_seed() -> None:
    corpus = [("spam", f"spam {index}") for index in range(50)]
    corpus += [("ham", f"ham {index}") for index in range(50)]

    assert stratified_split(corpus, seed=7) == stratified_split(corpus, seed=7)
    assert stratified_split(corpus, seed=7) != stratified_split(corpus, seed=8)


def test_english_ham_fixture_is_present_and_shaped() -> None:
    messages = load_english_ham()

    assert len(messages) >= 20
    assert all(isinstance(message, str) and message.strip() for message in messages)


def test_transcript_ham_teaches_english_vocabulary() -> None:
    """The whole point of the retrain: English ham must stop scoring as spam.

    Mirrors the real failure mode in miniature -- a spam-heavy corpus whose only
    ham is German -- and asserts that transcript lines fix it.
    """
    comments = [("spam", f"cheap replica watches buy now offer {index}") for index in range(40)]
    comments += [("ham", f"vielen dank fuer die folge sehr interessant {index}") for index in range(4)]

    english = "Anna anna@example.com Great episode, the Django testing discussion was helpful"

    without_transcripts = train_model(comments, [])
    assert without_transcripts.predict_label(english) == "spam"

    transcript_lines = [
        "Great to have you on the show to talk about Django and testing",
        "The episode discussion was helpful for anyone working with Django",
        "Welcome to another episode of the show, today we discuss testing",
    ] * 40
    with_transcripts = train_model(comments, transcript_lines)
    assert with_transcripts.predict_label(english) == "ham"


def test_model_to_json_round_trips_through_plain_dicts() -> None:
    model = train_model([("ham", "hello there"), ("spam", "buy now")], [])

    payload = model_to_json(model)
    reloaded = json.loads(json.dumps(payload))

    assert reloaded["class"] == "NaiveBayes"
    assert set(reloaded["prior_probabilities"]) == {"ham", "spam"}
    assert reloaded["word_label_counts"]["hello"] == {"ham": 1}


@pytest.fixture
def trained_payload(tmp_path: Path) -> Path:
    comments = [("spam", f"cheap replica watches buy now offer {index}") for index in range(30)]
    comments += [("ham", f"vielen dank fuer die folge {index}") for index in range(6)]
    lines = [
        "Loved the discussion about the Django ORM and excellent testing practices",
        "Super Folge, ich hoere den Podcast seit Jahren",
        "Anna and the guests talk about Django, episodes and the ORM discussion",
    ] * 60
    model = train_model(comments, lines)

    path = tmp_path / "payload.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            {"model": model_to_json(model), "performance": {"evaluated_on": "unit test"}},
            handle,
        )
    return path


@pytest.mark.django_db
def test_install_creates_row_and_runs_spot_checks(trained_payload: Path) -> None:
    out = StringIO()
    call_command(
        "install_django_chat_spamfilter",
        str(trained_payload),
        name="test-model",
        stdout=out,
    )

    spam_filter = spam_filters.get()
    assert spam_filter.name == "test-model"
    # Re-read went through ModelDecoder, so this is a real NaiveBayes again.
    assert spam_filter.model.predict_label("buy cheap replica watches now") == "spam"
    assert "Spot checks passed" in out.getvalue()


@pytest.mark.django_db
def test_install_refuses_to_overwrite_without_backup(trained_payload: Path) -> None:
    call_command(
        "install_django_chat_spamfilter",
        str(trained_payload),
        name="first",
        stdout=StringIO(),
    )

    with pytest.raises(CommandError, match="without --backup"):
        call_command(
            "install_django_chat_spamfilter",
            str(trained_payload),
            name="second",
            stdout=StringIO(),
        )

    assert spam_filters.get().name == "first"


@pytest.mark.django_db
def test_install_writes_backup_before_overwriting(trained_payload: Path, tmp_path: Path) -> None:
    call_command(
        "install_django_chat_spamfilter",
        str(trained_payload),
        name="first",
        stdout=StringIO(),
    )

    backup = tmp_path / "backup.json"
    call_command(
        "install_django_chat_spamfilter",
        str(trained_payload),
        name="second",
        backup=str(backup),
        stdout=StringIO(),
    )

    saved = json.loads(backup.read_text(encoding="utf-8"))
    assert saved["name"] == "first"
    assert saved["model"]["class"] == "NaiveBayes"
    assert spam_filters.get().name == "second"


@pytest.mark.django_db
def test_install_dry_run_leaves_database_untouched(trained_payload: Path) -> None:
    out = StringIO()
    call_command(
        "install_django_chat_spamfilter",
        str(trained_payload),
        name="test-model",
        dry_run=True,
        stdout=out,
    )

    assert not spam_filters.exists()
    assert "nothing written" in out.getvalue()


@pytest.mark.django_db
def test_install_rejects_ambiguous_multiple_rows(trained_payload: Path) -> None:
    spam_filters.create(name="one", model={}, performance={})
    spam_filters.create(name="two", model={}, performance={})

    with pytest.raises(CommandError, match="expected at most one"):
        call_command(
            "install_django_chat_spamfilter",
            str(trained_payload),
            name="three",
            stdout=StringIO(),
        )


@pytest.mark.django_db
def test_install_rejects_payload_that_is_not_naive_bayes(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"model": {"class": "SomethingElse"}, "performance": {}}, handle)

    with pytest.raises(CommandError, match="not a NaiveBayes model"):
        call_command(
            "install_django_chat_spamfilter", str(path), name="bad", stdout=StringIO()
        )


def test_extract_corpus_command_writes_json(tmp_path: Path) -> None:
    dump = write_dump(tmp_path)
    output = tmp_path / "corpus.json"
    out = StringIO()

    call_command(
        "extract_django_chat_spam_corpus", str(dump), output=str(output), stdout=out
    )

    corpus = json.loads(output.read_text(encoding="utf-8"))
    assert len(corpus) == 3
    assert "Extracted 3 comments" in out.getvalue()


def test_extract_corpus_command_errors_on_missing_dump(tmp_path: Path) -> None:
    with pytest.raises(CommandError, match="Dump not found"):
        call_command(
            "extract_django_chat_spam_corpus",
            str(tmp_path / "nope.sql"),
            output=str(tmp_path / "out.json"),
            stdout=StringIO(),
        )


def test_train_command_reports_scores_and_writes_payload(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus.json"
    corpus = [["spam", f"cheap replica watches buy now {index}"] for index in range(40)]
    corpus += [["ham", f"vielen dank fuer die folge {index}"] for index in range(10)]
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    ham_path = tmp_path / "lines.json"
    ham_path.write_text(
        json.dumps(
            [
                "Great episode about Django and the testing discussion was helpful",
                "Thanks for having the guests on to talk about Django and episodes",
            ]
            * 50
        ),
        encoding="utf-8",
    )

    output = tmp_path / "model.json"
    out = StringIO()
    call_command(
        "train_django_chat_spamfilter",
        corpus=str(corpus_path),
        transcript_ham=str(ham_path),
        output=str(output),
        ham_lines=60,
        stdout=out,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["model"]["class"] == "NaiveBayes"
    assert payload["evaluation"]["transcript_ham_lines"] == 60
    assert "evaluated_on" in payload["performance"]
    assert "spam recall" in out.getvalue()


def test_train_command_rejects_more_ham_lines_than_available(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(
        json.dumps([["spam", "buy now"], ["ham", "danke schoen"]]), encoding="utf-8"
    )
    ham_path = tmp_path / "lines.json"
    ham_path.write_text(json.dumps(["one line"]), encoding="utf-8")

    with pytest.raises(CommandError, match="exceeds the 1 available"):
        call_command(
            "train_django_chat_spamfilter",
            corpus=str(corpus_path),
            transcript_ham=str(ham_path),
            ham_lines=5,
            stdout=StringIO(),
        )
