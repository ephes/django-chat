"""Tooling to train django-cast's comment `SpamFilter` for Django Chat.

The imported python-podcast model classifies English ham as spam, because its
ham class is almost entirely German. These modules rebuild the model from the
python-podcast comment corpus plus Django Chat transcript lines, which supply
the missing English vocabulary. See `docs/spam-filter.md`.
"""

from __future__ import annotations

from django_chat.core.spamfilter.corpus import (
    LabelledMessage,
    extract_comment_corpus,
    label_counts,
)
from django_chat.core.spamfilter.training import (
    DEFAULT_SEED,
    DEFAULT_TRANSCRIPT_HAM_LINES,
    EvaluationResult,
    build_spamfilter_payload,
    evaluate_model,
    load_english_ham,
    model_to_json,
    stratified_split,
    train_model,
)

__all__ = [
    "DEFAULT_SEED",
    "DEFAULT_TRANSCRIPT_HAM_LINES",
    "EvaluationResult",
    "LabelledMessage",
    "build_spamfilter_payload",
    "evaluate_model",
    "extract_comment_corpus",
    "label_counts",
    "load_english_ham",
    "model_to_json",
    "stratified_split",
    "train_model",
]
