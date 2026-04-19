# Repository Guidelines

## Project Context

This repository is for a self-hosted Django Chat site based on Django,
Wagtail, and django-cast.

The planning source of truth is:

- `2026-04-18_django-chat_research.md`

`../python-podcast` is a read-only structural reference for project shape,
local commands, and deployment ergonomics. Do not modify it. Do not copy
Python Podcast-specific branding, content, routes, legal pages, social links,
comments, account flows, Fediverse proxy routes, API endpoints, secrets, or
deployment configuration unless a Django Chat-specific requirement says to do
so.

## Commands And Tooling

- Use `just --list` to discover available commands once the project scaffold
  exists.
- Use `just install` for dependency installation when available.
- Use `just manage ...` for Django management commands when available.
- Use `just test` for the Python test suite when available.
- Python tests should use `pytest`.
- Hook tooling may be `prek` or `pre-commit`; use whichever is configured in
  the repo. Do not introduce both without a clear reason.

If a command is not available yet because the project is still being
scaffolded, add the missing command as part of the relevant implementation
slice rather than inventing an unrelated workflow.

## Quality Gates

Before considering implementation work complete, run the relevant quality
gates:

- `just test`
- the configured hook runner (check which tool is configured before running;
  do not assume a specific invocation)
- any narrower checks documented for the current slice

Do not claim work is ready to commit until tests are green and the configured
hooks pass. If a quality gate cannot be run, state the exact command, why it
could not be run, and what was verified instead in the handoff notes or final
response.

## Documentation And Changelog

Implementation and review work is not complete until documentation matches the
change when behavior, workflow, deployment, or user-facing usage changes.

Before committing or handing off work:

- Check whether README, setup docs, operational docs, or the PRD need updates.
- Check whether a changelog or release-notes convention exists.
- Update the relevant docs or changelog when they apply.
- If no changelog/release-notes convention exists, state that explicitly in the
  handoff instead of creating one casually.

## Git And Commits

- Do not run `git commit`, `git push`, or destructive git commands unless the
  user explicitly asks for them.
- Before committing, ensure tests and configured hooks pass, docs are current,
  and `git status --short` contains only intended changes.
- Keep commits scoped to one logical change.
- Do not refer to yourself or to Anthropic in commit messages.
- Do not add generated-by watermarks or emoji signatures to commit messages.

## Secrets And Access

Never commit real secrets or environment-specific credentials, including:

- S3 credentials or bucket secrets
- database passwords
- Django secret keys
- Sentry DSNs
- Mailgun keys
- admin passwords
- SOPS keys or decrypted secret files

Deployment secrets and private operations repositories must stay outside this
shareable app repo unless the PRD is explicitly revised.
