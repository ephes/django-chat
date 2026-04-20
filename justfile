# Local commands for the Django Chat scaffold.

default:
    @just --list

install:
    uv sync

lint:
    uv run ruff check .

format:
    uv run ruff check --fix .
    uv run ruff format .

format-check:
    uv run ruff format --check .

typecheck:
    uv run ty check config django_chat manage.py

check:
    just lint
    just format-check
    just typecheck
    just test

manage *ARGS:
    uv run python manage.py {{ARGS}}

test *ARGS:
    uv run pytest {{ARGS}}

runserver *ARGS:
    uv run python manage.py runserver {{ARGS}}
