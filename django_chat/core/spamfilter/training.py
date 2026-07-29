"""Train and evaluate the Django Chat comment spam filter.

`NaiveBayes` and `regex_tokenize` are imported from django-cast rather than
reimplemented, so the JSON written to `cast_spamfilter.model` always matches what
`cast.models.moderation.ModelDecoder` and `predict()` expect at runtime.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from cast.models.moderation import NaiveBayes, regex_tokenize

from django_chat.core.spamfilter.corpus import LabelledMessage

# Transcript-ham size actually shipped. More transcript ham buys English-ham
# accuracy and costs spam recall; 40k clears the synthetic English ham set with a
# real margin, where 30k left one message misfiled at p(spam) = 0.54. A hidden
# legitimate comment costs more than a published spam comment a human can still
# moderate. See docs/spam-filter.md for the full curve.
DEFAULT_TRANSCRIPT_HAM_LINES = 40_000

DEFAULT_SEED = 20260729
DEFAULT_TEST_FRACTION = 0.2

ENGLISH_HAM_FIXTURE = Path(__file__).parent / "fixtures" / "english_ham.json"


def load_english_ham() -> list[str]:
    """Synthetic English ham messages, held out for evaluation only.

    These are never trained on: they exist to measure the failure mode that made
    the imported python-podcast model unusable (English ham scored as spam).
    """
    with ENGLISH_HAM_FIXTURE.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return list(payload["messages"])


def stratified_split(
    corpus: list[LabelledMessage],
    test_fraction: float = DEFAULT_TEST_FRACTION,
    seed: int = DEFAULT_SEED,
) -> tuple[list[LabelledMessage], list[LabelledMessage]]:
    """Split `corpus` into train/test, preserving each label's proportion.

    The ham class is tiny (~189 of ~9,750), so an unstratified split can leave
    the test set with almost no ham at all.
    """
    by_label: dict[str, list[LabelledMessage]] = defaultdict(list)
    for label, message in corpus:
        by_label[label].append((label, message))

    rng = random.Random(seed)
    train: list[LabelledMessage] = []
    test: list[LabelledMessage] = []
    for label in sorted(by_label):
        items = list(by_label[label])
        rng.shuffle(items)
        cut = int(len(items) * (1 - test_fraction))
        train.extend(items[:cut])
        test.extend(items[cut:])
    return train, test


def sample_ham_lines(lines: list[str], count: int, seed: int = DEFAULT_SEED) -> list[str]:
    """Deterministically sample `count` transcript lines to use as ham."""
    shuffled = list(lines)
    random.Random(seed).shuffle(shuffled)
    return shuffled[:count]


def train_model(comments: list[LabelledMessage], ham_lines: list[str]) -> NaiveBayes:
    """Fit a model on labelled comments plus transcript lines labelled ham."""
    training_data = list(comments) + [("ham", line) for line in ham_lines]
    return NaiveBayes(tokenize=regex_tokenize).fit(training_data)


def recall(model: NaiveBayes, messages: list[LabelledMessage]) -> float:
    """Fraction of `messages` whose true label the model predicts."""
    if not messages:
        return float("nan")
    hits = sum(1 for label, message in messages if model.predict_label(message) == label)
    return hits / len(messages)


def worst_ham_margin(model: NaiveBayes, messages: list[LabelledMessage]) -> float:
    """Highest p(spam) assigned to any message in `messages`.

    Ham that merely lands on the right side of the boundary is fragile; this
    reports how close the closest call actually was.
    """
    if not messages:
        return float("nan")
    return max(model.predict(message).get("spam", 0.0) for _label, message in messages)


@dataclass
class EvaluationResult:
    """Held-out scores for a trained model."""

    spam_recall: float
    german_ham_recall: float
    english_ham_recall: float
    worst_english_ham_p_spam: float
    spam_count: int
    german_ham_count: int
    english_ham_count: int
    performance: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "held_out_spam_recall": self.spam_recall,
            "held_out_de_ham_recall": self.german_ham_recall,
            "synthetic_en_ham_recall": self.english_ham_recall,
            "worst_en_ham_p_spam": self.worst_english_ham_p_spam,
            "held_out_spam_count": self.spam_count,
            "held_out_de_ham_count": self.german_ham_count,
            "synthetic_en_ham_count": self.english_ham_count,
        }


def _precision_recall_f1(
    true_positive: int, false_positive: int, false_negative: int
) -> dict[str, float]:
    predicted = true_positive + false_positive
    actual = true_positive + false_negative
    precision = true_positive / predicted if predicted else 0.0
    rec = true_positive / actual if actual else 0.0
    f1 = 2 * precision * rec / (precision + rec) if precision + rec else 0.0
    return {"precision": precision, "recall": rec, "f1": f1}


def comment_performance(
    model: NaiveBayes, evaluation_set: list[LabelledMessage]
) -> dict[str, object]:
    """Per-label precision/recall/f1 over a held-out *comment* set.

    django-cast's own `retrain_from_scratch` scores whatever it was trained on,
    which for us includes transcript lines — that measures a
    comment-vs-transcript task, not comment classification. This scores the task
    anyone actually cares about, and records what it was computed over.
    """
    true_positive: dict[str, int] = defaultdict(int)
    false_positive: dict[str, int] = defaultdict(int)
    false_negative: dict[str, int] = defaultdict(int)
    for label, message in evaluation_set:
        predicted = model.predict_label(message)
        if predicted == label:
            true_positive[label] += 1
        else:
            false_negative[label] += 1
            if predicted is not None:
                false_positive[predicted] += 1

    performance: dict[str, object] = {}
    for label in ("ham", "spam"):
        performance[label] = _precision_recall_f1(
            true_positive[label], false_positive[label], false_negative[label]
        )
    return performance


def evaluate_model(
    model: NaiveBayes,
    test_comments: list[LabelledMessage],
    english_ham: list[str],
) -> EvaluationResult:
    """Score a model on held-out comments plus the synthetic English ham set."""
    test_spam = [item for item in test_comments if item[0] == "spam"]
    test_german_ham = [item for item in test_comments if item[0] == "ham"]
    english = [("ham", message) for message in english_ham]

    evaluation_set = test_spam + test_german_ham + english
    performance = comment_performance(model, evaluation_set)
    performance["evaluated_on"] = (
        f"held-out comments ({len(test_spam)} spam, {len(test_german_ham)} de ham) plus "
        f"{len(english)} synthetic English ham; NOT the mixed training set"
    )

    return EvaluationResult(
        spam_recall=recall(model, test_spam),
        german_ham_recall=recall(model, test_german_ham),
        english_ham_recall=recall(model, english),
        worst_english_ham_p_spam=worst_ham_margin(model, english),
        spam_count=len(test_spam),
        german_ham_count=len(test_german_ham),
        english_ham_count=len(english),
        performance=performance,
    )


def model_to_json(model: NaiveBayes) -> dict[str, object]:
    """Serialise a fitted model into plain JSON-safe structures.

    `NaiveBayes.dict()` hands back nested defaultdicts; those serialise fine but
    compare and round-trip badly, so flatten them here.
    """
    payload = model.dict()
    payload["word_label_counts"] = {
        word: dict(counts) for word, counts in payload["word_label_counts"].items()
    }
    payload["prior_probabilities"] = dict(payload["prior_probabilities"])
    return payload


def build_spamfilter_payload(
    model: NaiveBayes,
    evaluation: EvaluationResult,
    *,
    train_comment_count: int,
    transcript_ham_lines: int,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    """Assemble the JSON written to `cast_spamfilter` plus provenance metadata."""
    return {
        "model": model_to_json(model),
        "performance": evaluation.performance,
        "evaluation": {
            **evaluation.as_dict(),
            "train_comments": train_comment_count,
            "transcript_ham_lines": transcript_ham_lines,
            "seed": seed,
            "vocabulary_tokens": len(model.word_label_counts),
        },
    }
