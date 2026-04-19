# Local commands for the Django Chat scaffold.

default:
    @just --list

install:
    uv sync

manage *ARGS:
    uv run python manage.py {{ARGS}}

test *ARGS:
    uv run pytest {{ARGS}}

runserver *ARGS:
    uv run python manage.py runserver {{ARGS}}
