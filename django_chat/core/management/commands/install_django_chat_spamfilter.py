from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cast.models.moderation import SpamFilter
from django.core.management.base import BaseCommand, CommandError, CommandParser

SPOT_CHECKS: tuple[tuple[str, str], ...] = (
    (
        "ham",
        "Anna anna@example.com Loved this episode, the discussion about the Django ORM "
        "was excellent. Thanks!",
    ),
    (
        "ham",
        "Jens jens@example.de Super Folge, ich hoere den Podcast seit Jahren. Weiter so!",
    ),
    (
        "spam",
        "Outlet spam@spam.biz Cheap replica watches handbags outlet online store free "
        "shipping buy now click here",
    ),
)


class Command(BaseCommand):
    help = (
        "Install a trained spam-filter model into cast_spamfilter, replacing the single "
        "existing row. Backs up the current model first and verifies the installed model "
        "through the real decode path before finishing."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "payload",
            type=Path,
            help="Model payload JSON from train_django_chat_spamfilter.",
        )
        parser.add_argument(
            "--name",
            required=True,
            help="Name to store on the SpamFilter row, e.g. 2026-07-29-transcript-ham.",
        )
        parser.add_argument(
            "--backup",
            type=Path,
            help="Write the current row to this path before overwriting it.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change and exit without writing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # call_command(...) bypasses argparse's type coercion, so normalise here.
        payload_path = Path(options["payload"])
        name: str = options["name"]
        backup = Path(options["backup"]) if options["backup"] else None
        dry_run: bool = options["dry_run"]

        if not payload_path.exists():
            raise CommandError(f"Payload not found: {payload_path}")

        with payload_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        for key in ("model", "performance"):
            if key not in payload:
                raise CommandError(f"Payload is missing '{key}': {payload_path}")
        if payload["model"].get("class") != "NaiveBayes":
            raise CommandError("Payload model is not a NaiveBayes model.")

        # get_default() is SpamFilter.objects.first() and the model declares no
        # ordering, so a second row makes which filter is live undefined. Always
        # update in place.
        # ty cannot see the implicit manager on cast's SpamFilter model.
        existing = list(SpamFilter.objects.order_by("id"))  # ty: ignore[unresolved-attribute]
        if len(existing) > 1:
            raise CommandError(
                f"Found {len(existing)} SpamFilter rows; expected at most one. "
                "Remove the extras first -- get_default() would be ambiguous."
            )

        if existing:
            current = existing[0]
            self.stdout.write(
                f"current: id={current.id} name={current.name!r} "
                f"tokens={len(current.model.word_label_counts)}"
            )
            if backup is not None:
                backup.parent.mkdir(parents=True, exist_ok=True)
                with backup.open("w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "id": current.id,
                            "name": current.name,
                            "model": current.model.dict(),
                            "performance": current.performance,
                        },
                        handle,
                        default=dict,
                    )
                self.stdout.write(f"backed up current row -> {backup}")
            elif not dry_run:
                raise CommandError(
                    "Refusing to overwrite the existing model without --backup. "
                    "Pass --backup PATH (or --dry-run to preview)."
                )
        else:
            self.stdout.write("no existing SpamFilter row; a new one will be created")

        token_count = len(payload["model"].get("word_label_counts", {}))
        self.stdout.write(
            f"incoming: name={name!r} tokens={token_count} "
            f"priors={payload['model'].get('prior_probabilities')}"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run: nothing written."))
            return

        spam_filter = existing[0] if existing else SpamFilter()
        spam_filter.name = name  # ty: ignore[invalid-assignment]
        spam_filter.model = payload["model"]
        spam_filter.performance = payload["performance"]
        spam_filter.save()

        # Re-read so the check exercises ModelDecoder rather than the dict we
        # just assigned.
        spam_filter = SpamFilter.objects.get(pk=spam_filter.pk)  # ty: ignore[unresolved-attribute]
        self.stdout.write(
            f"installed: id={spam_filter.id} name={spam_filter.name!r} "
            f"tokens={len(spam_filter.model.word_label_counts)}"
        )

        failures = []
        for expected, message in SPOT_CHECKS:
            predicted = spam_filter.model.predict_label(message)
            probability = spam_filter.model.predict(message).get("spam", 0.0)
            status = "ok" if predicted == expected else "MISMATCH"
            if predicted != expected:
                failures.append((expected, predicted, message))
            self.stdout.write(
                f"  {status:<8} expected={expected:<4} got={predicted!s:<4} "
                f"p(spam)={probability:.4f}"
            )

        if failures:
            raise CommandError(
                f"{len(failures)} spot check(s) failed against the installed model. "
                "Restore the backup before enabling comments."
            )
        self.stdout.write(self.style.SUCCESS("Spot checks passed."))
