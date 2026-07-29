# Comment spam filter

Django Chat uses django-cast's native `SpamFilter`
(`cast.models.moderation.SpamFilter`) — a Naive Bayes classifier stored as JSON
in the `cast_spamfilter` table — together with `cast.moderation.Moderator` and
the comment form's honeypot field. See
[Local development](local-development.md#comments) for how comments are enabled.

With **no** trained filter the moderator sees `predicted_label = "unknown"` and
publishes every comment. That is the safe-but-unfiltered default. Only
`predicted_label == "spam"` hides a comment (`is_public=False`,
`is_removed=True`); both `"ham"` and `"unknown"` publish.

## Current state

Staging runs the model named **`2026-07-29-transcript-ham`** (`cast_spamfilter`
row 1, 120,094 tokens, priors ham 84.0% / spam 16.0%), trained on 2026-07-29
from 7,797 python-podcast comments plus 40,000 Django Chat transcript lines as
English ham. Measured on held-out data:

| | value |
| --- | --- |
| held-out spam recall | 98.3% (1,912 spam) |
| held-out German ham | 100.0% (38 messages) |
| synthetic English ham | 100.0% (25 messages) |
| worst English ham margin | `p(spam) = 0.013` |

Verified end-to-end through `cast.moderation.Moderator.moderate()` on staging
with the real `CastComment` model: English and German ham publish, obvious spam
is hidden. The previous model is backed up on the staging host at
`/root/spamfilter-backup-20260729.json`.

This applies to staging only — there is no production environment yet (slice 8;
the production host in `deploy/inventory/hosts.yml` is still a placeholder), and
`deploy/group_vars/django_chat.yml` keeps `comments_enabled` false for everything
that inherits the shared default. Local development has no `cast_spamfilter` row
at all, so the moderator publishes every comment there.

## Why the previously imported model was not usable

The filter on staging was first seeded on 2026-07-27 by copying the trained model
out of `../python-podcast`'s production `cast_spamfilter` row (name
`2022-11-20`, 43,159 tokens, priors spam 94.3% / ham 5.7%). It was replaced on
2026-07-29 for the reasons below.

**That model was unusable for Django Chat.** The python-podcast comment corpus
is ~9,750 comments of which only 189 are ham, and those are almost all German —
the rest is mostly English bot text. (Live production read on 2026-07-27: 9,750
total / 9,561 spam / 189 ham. The 2026-06-30 dump used for the retrain below:
9,747 / 9,558 / 189.) Its ham class contains no English examples at all, so
English vocabulary only ever appears in the spam class. In effect it is a
German-vs-English classifier, not a ham-vs-spam one.

Measured against the copied model on staging (2026-07-27):

- **5/5 synthetic English ham messages classified spam at `p = 1.0000`**
- 2/5 German ham messages false-positived

Django Chat is an English-language podcast, so the imported filter would have
hidden essentially every legitimate comment.

The `performance` JSON stored alongside it (ham f1 0.94, spam f1 0.997) was
python-podcast's own cross-validation score on its own corpus. It said nothing
about Django Chat and should not have been read as reassurance.

## The fix: transcript lines as English ham

Adding Django Chat **transcript lines** as ham training data repairs the filter.
Retrained from the real corpus with a stratified 80/20 split (1,912 held-out
spam, 38 held-out German ham, 25 synthetic English ham, seed `20260729`):

| training data | spam recall | de ham | en ham |
| --- | --- | --- | --- |
| comments only (baseline) | 100.0% | 89.5% | 0.0% |
| + 10,000 transcript lines | 100.0% | 97.4% | 72.0% |
| + 30,000 transcript lines | 99.2% | 100.0% | 96.0% |
| **+ 40,000 transcript lines (shipped)** | **98.3%** | **100.0%** | **100.0%** |
| + 60,000 transcript lines | 96.5% | 100.0% | 100.0% |
| + all 130,072 transcript lines | 93.3% | 100.0% | 100.0% |

More transcript ham trades spam recall for English ham accuracy. **40,000 lines
is the chosen operating point.** An earlier pass called ≈30,000 the sweet spot,
but at 30k the one surviving English ham failure sits at `p(spam) = 0.54` —
on the wrong side of the boundary with no margin at all. Going to 40k clears
English ham outright (worst case `p(spam) = 0.013`) and costs 0.9pp of spam
recall, about 17 additional spam comments per 1,912.

That trade is deliberate: a false positive silently hides a real listener
comment, while a false negative publishes a spam comment that a human can still
moderate — and moderating it *improves* the corpus, since django-cast keeps
removed comments as training examples. For a low-volume comment section,
recall of ham matters more than recall of spam. Note that 95% of held-out spam
still scores `p(spam) = 1.0000`, so the loss is concentrated in genuinely
ambiguous messages.

An ablation confirms the gain is **vocabulary, not the shifted prior**
(re-measured 2026-07-29 on the shipped split):

| variant | spam recall | de ham | en ham |
| --- | --- | --- | --- |
| baseline vocabulary + baseline prior (ham 1.9%) | 100.0% | 89.5% | 0.0% |
| baseline vocabulary + prior forced to 94% ham | 100.0% | 89.5% | **0.0%** |
| 40k vocabulary + prior pinned to baseline | 98.5% | 97.4% | **96.0%** |
| 40k vocabulary + its own prior (shipped) | 98.3% | 100.0% | 100.0% |

Forcing the prior to 94% ham while keeping baseline vocabulary changes *nothing* —
English ham stays at 0%. Conversely the 40k vocabulary recovers 96% of English ham
even with the original prior pinned back on. The vocabulary is doing the work.

Filtering the transcript lines to 8–60 words and deduplicating makes no material
difference (97.8% / 100% / 100%), so the extractor keeps it simple and does
neither.

The earlier pass also found show notes alone useless as ham (205 episode bodies,
~17k words, left English ham at 0%) — plausible given transcripts carry ~2M words,
but not re-verified here.

Transcript text is reachable as `Transcript.dote` JSON → `lines[].text`
(130,072 lines, ~2M words, median 17 words/line across the 205 staging
episodes).

## Operational cautions

- **The admin "Retrain" action is destructive here.** It calls
  `retrain_from_scratch(get_training_data_comments())`, which reads the *local*
  `django_comments` table. That table has 0 rows on staging, so running it would
  discard both the ~9,558-example spam corpus and the transcript ham — i.e. the
  entire trained model — and replace it with nothing. Do not use it until the
  site has a meaningful number of its own labelled comments.
- **`performance` is meaningless after mixing in transcripts.** The JSON that
  `retrain_from_scratch` stores is computed over the mixed training set, so it
  scores a comment-vs-transcript task, not comment classification. The
  `performance` currently stored on staging was instead computed over held-out
  comments plus the synthetic English ham, and carries an `evaluated_on` key
  saying so. Keep that convention.
- **Rollback:** restore the pre-retrain model from
  `/root/spamfilter-backup-20260729.json` on the staging host, or drop the filter
  entirely with `delete from cast_spamfilter;`, which returns the site to
  `predicted_label = "unknown"` → every comment published. Dropping it is
  strictly safer than leaving a known-bad filter in place.
- **Exposure is one checkbox.** `CAST_COMMENTS_ENABLED` is already `true` on
  staging (`deploy/group_vars/staging.yml`), and all 205 episodes have
  `comments_enabled = true`. Only the podcast-level `comments_enabled` toggle on
  the Podcast page is holding comments closed. Ticking it activates the catalog
  *and* whatever filter is in `cast_spamfilter` at that moment.

## Model format

`SpamFilter.model` is JSON with three keys:

```json
{
  "class": "NaiveBayes",
  "prior_probabilities": {"ham": 0.8400318011590686, "spam": 0.15996819884093144},
  "word_label_counts": {"word": {"ham": 3, "spam": 41}}
}
```

(`prior_probabilities` above are the values currently on staging;
`word_label_counts` holds one entry per token.)

Messages are built by `SpamFilter.comment_to_message` as
`"{name} {email} {title} {comment}"` and tokenized by the regex
`(?u)\b\w\w+\b` after lowercasing. Any script that writes this table directly
must match both, or the stored counts will not line up with what `predict()`
looks up at runtime.

The runtime comment model is `cast.comments.models.CastComment` — a **proxy** over
`threadedcomments.ThreadedComment` while `USE_THREADEDCOMMENTS` is on (its MRO is
`CastComment → ThreadedComment → Comment`, `db_table = threadedcomments_comment`).
Because `ThreadedComment` uses multi-table inheritance, `title` lives in
`threadedcomments_comment` while the rest of the fields live in
`django_comments` — a SQL-level corpus extractor has to join the two.

## How to retrain

Four management commands cover the pipeline, in
`django_chat/core/management/commands/`, with the shared logic in
`django_chat/core/spamfilter/`. They are split by *where each step has to run*:
corpus extraction needs the python-podcast dump, transcript extraction needs the
app's transcript storage, and only the last step touches the database.

**1. Labelled comments** — from a python-podcast dump, so python-podcast
production is never touched:

```console
uv run python manage.py extract_django_chat_spam_corpus \
    ../python-podcast/backups/2026-06-30-132744_python-podcast.sql.gz \
    --output /tmp/comment_corpus.json
```

Joins `django_comments` to `threadedcomments_comment` for `title`, skips
author-deleted rows, and labels
`ham if (is_public and not is_removed) else spam` — matching
`SpamFilter.get_training_data_comments`. Warns if the ham class is too small to
teach English ham on its own.

**2. Transcript ham** — must run where transcript storage is reachable, i.e. on
the staging host via its deployed venv, not a bare local checkout:

```console
uv run python manage.py extract_django_chat_transcript_ham \
    --output /tmp/transcript_lines.json
```

**3. Train and evaluate** — no database access; writes the model payload:

```console
uv run python manage.py train_django_chat_spamfilter \
    --corpus /tmp/comment_corpus.json \
    --transcript-ham /tmp/transcript_lines.json \
    --output /tmp/model.json
```

Defaults to `--ham-lines 40000` and seed `20260729`. Add `--sweep` to re-derive
the trade-off table above before committing to an operating point. It reports
held-out spam / German-ham / English-ham recall plus the worst English-ham
margin, and warns when English ham is not fully clean. Omit `--output` to
evaluate without writing anything.

**4. Install** — the only step that writes to `cast_spamfilter`:

```console
uv run python manage.py install_django_chat_spamfilter /tmp/model.json \
    --name 2026-07-30-transcript-ham \
    --backup /root/spamfilter-backup-20260730.json
```

It refuses to overwrite an existing model without `--backup`, refuses to run at
all if more than one row exists (`get_default()` is `SpamFilter.objects.first()`
with no declared ordering, so two rows make the live filter undefined), updates
the single row in place, then re-reads it from the database — exercising
`ModelDecoder` — and runs English/German ham plus spam spot checks, failing if
any mismatch. `--dry-run` previews without writing.

Finally confirm through the moderation path rather than the model alone, since
`Moderator` is what actually decides visibility:

```console
uv run python manage.py shell -c "
from cast.moderation import Moderator
from django_comments import get_model
Comment = get_model()
c = Comment(user_name='Anna', user_email='anna@example.com',
            comment='Great episode, the Django ORM discussion was excellent.')
c.title = ''
print('hidden' if Moderator(model=Comment).moderate(c, None, None) else 'published')
"
```

The 25-message English ham set lives at
`django_chat/core/spamfilter/fixtures/english_ham.json` and is
**evaluation-only** — never training data.
`django_chat/core/tests/test_spamfilter.py` covers the dump parser (COPY escapes,
gzip, author-deleted exclusion), the stratified split, the
transcript-ham-fixes-English-ham property, and the install command's safety
rails.

This pipeline reproduces the shipped model exactly: re-running steps 1–3 against
the 2026-06-30 dump yields byte-identical `word_label_counts` and priors to the
row live on staging.
