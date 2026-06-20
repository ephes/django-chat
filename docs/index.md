# Django Chat documentation

Self-hosted **Django Chat** site, built with Django, Wagtail, and django-cast.

This site renders the operational, development, and design docs that live under
`docs/`. Serve it locally with `just docs` (optionally `just docs <port>`), or
build a static copy into `site/` with `just docs-build`.

The canonical planning source of truth lives outside this site, in
`2026-04-18_django-chat_research.md` at the repository root.

## Development

- [Local development](local-development.md) — getting the site running locally,
  media backends, and day-to-day workflow.
- [CSS architecture](css-architecture.md) — how the stylesheets are structured.

## Deployment & operations

- [Deployment](deployment.md) — deploying the site, with the security and
  ownership boundary in [Operations boundary](operations-boundary.md).
- [Staging differences](staging-differences.md) — how staging diverges from
  local and production.
- [Host review guide](host-review-guide.md) — what hosts should check on
  staging.
- [Production migration notes](production-migration-notes.md) — notes for the
  move to production.

## Features & specs

- [Custom player, transcript & sharing](custom-player-transcript-share-spec.md)
- [Structured show-note blocks](structured-show-note-blocks-research.md)
- [Contributors & diarization](contributors-and-diarization.md)
- [Episode numbering](episode-numbering-research.md)

## Data & migration

- [Feed cutover analysis](feed-cutover-analysis.md)
- [Show-note backfill & repair](show-note-backfill-repair.md)

## Security

- [Import security](import-security.md)
- [Known security issues](security-known-issues.md)

## Quality

- [Lighthouse performance](lighthouse-performance.md)

## Project status

- [Implementation status](implementation-status.md)
