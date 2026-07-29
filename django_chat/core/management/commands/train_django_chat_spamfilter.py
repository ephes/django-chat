from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_chat.core.spamfilter.training import (
    DEFAULT_SEED,
    DEFAULT_TRANSCRIPT_HAM_LINES,
    build_spamfilter_payload,
    evaluate_model,
    load_english_ham,
    sample_ham_lines,
    stratified_split,
    train_model,
)


class Command(BaseCommand):
    help = (
        "Train the comment spam filter from a labelled comment corpus plus Django Chat "
        "transcript lines used as English ham, and report held-out scores. Writes the "
        "model JSON for install_django_chat_spamfilter; does not touch the database."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--corpus",
            type=Path,
            required=True,
            help="Labelled corpus JSON from extract_django_chat_spam_corpus.",
        )
        parser.add_argument(
            "--transcript-ham",
            type=Path,
            required=True,
            help="Transcript lines JSON from extract_django_chat_transcript_ham.",
        )
        parser.add_argument(
            "--output",
            type=Path,
            help="Where to write the trained model payload. Omit to evaluate only.",
        )
        parser.add_argument(
            "--ham-lines",
            type=int,
            default=DEFAULT_TRANSCRIPT_HAM_LINES,
            help=(
                "How many transcript lines to train on as ham. "
                f"Defaults to {DEFAULT_TRANSCRIPT_HAM_LINES}."
            ),
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=DEFAULT_SEED,
            help=f"RNG seed for the split and line sample. Defaults to {DEFAULT_SEED}.",
        )
        parser.add_argument(
            "--sweep",
            action="store_true",
            help=(
                "Also report the spam-recall / English-ham trade-off across a range of "
                "transcript-ham sizes, to re-derive the operating point."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # call_command(...) passes kwargs straight through without argparse's
        # type coercion, so normalise paths here rather than trusting the parser.
        corpus_path = Path(options["corpus"])
        ham_path = Path(options["transcript_ham"])
        output = Path(options["output"]) if options["output"] else None
        ham_lines: int = options["ham_lines"]
        seed: int = options["seed"]

        for path in (corpus_path, ham_path):
            if not path.exists():
                raise CommandError(f"Input not found: {path}")

        with corpus_path.open(encoding="utf-8") as handle:
            corpus = [(label, message) for label, message in json.load(handle)]
        with ham_path.open(encoding="utf-8") as handle:
            transcript_lines: list[str] = json.load(handle)

        if ham_lines > len(transcript_lines):
            raise CommandError(
                f"--ham-lines={ham_lines} exceeds the {len(transcript_lines)} available "
                "transcript lines."
            )

        english_ham = load_english_ham()
        train_comments, test_comments = stratified_split(corpus, seed=seed)
        spam_count = sum(1 for label, _ in test_comments if label == "spam")
        german_count = len(test_comments) - spam_count
        self.stdout.write(
            f"train comments: {len(train_comments)}  held-out spam: {spam_count}  "
            f"held-out de ham: {german_count}  en ham: {len(english_ham)}"
        )

        if options["sweep"]:
            self._sweep(train_comments, test_comments, english_ham, transcript_lines, seed)

        model = train_model(
            train_comments, sample_ham_lines(transcript_lines, ham_lines, seed=seed)
        )
        evaluation = evaluate_model(model, test_comments, english_ham)

        self.stdout.write("")
        self.stdout.write(f"trained on {ham_lines} transcript ham lines")
        self.stdout.write(f"  vocabulary:      {len(model.word_label_counts)} tokens")
        self.stdout.write(f"  priors:          {model.prior_probabilities}")
        self.stdout.write(f"  spam recall:     {evaluation.spam_recall:.1%}")
        self.stdout.write(f"  de ham recall:   {evaluation.german_ham_recall:.1%}")
        self.stdout.write(f"  en ham recall:   {evaluation.english_ham_recall:.1%}")
        self.stdout.write(
            f"  worst en ham:    p(spam) = {evaluation.worst_english_ham_p_spam:.4f}"
        )

        if evaluation.english_ham_recall < 1.0:
            self.stdout.write(
                self.style.WARNING(
                    "English ham is not fully clean; this filter would hide legitimate "
                    "comments. Try more --ham-lines before installing."
                )
            )

        if output is None:
            self.stdout.write("\nNo --output given; nothing written.")
            return

        payload = build_spamfilter_payload(
            model,
            evaluation,
            train_comment_count=len(train_comments),
            transcript_ham_lines=ham_lines,
            seed=seed,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        self.stdout.write(f"\nWrote model payload -> {output}")

    def _sweep(
        self,
        train_comments: list[tuple[str, str]],
        test_comments: list[tuple[str, str]],
        english_ham: list[str],
        transcript_lines: list[str],
        seed: int,
    ) -> None:
        sizes = [0, 10_000, 30_000, 40_000, 60_000, len(transcript_lines)]
        sizes = sorted({size for size in sizes if size <= len(transcript_lines)})
        self.stdout.write("")
        self.stdout.write(f"{'ham lines':>12} {'spam recall':>12} {'de ham':>8} {'en ham':>8}")
        self.stdout.write("-" * 44)
        for size in sizes:
            model = train_model(
                train_comments, sample_ham_lines(transcript_lines, size, seed=seed)
            )
            result = evaluate_model(model, test_comments, english_ham)
            self.stdout.write(
                f"{size:>12,} {result.spam_recall:>11.1%} "
                f"{result.german_ham_recall:>7.1%} {result.english_ham_recall:>7.1%}"
            )
