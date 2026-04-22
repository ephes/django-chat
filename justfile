# Local commands for the Django Chat scaffold.

ANSIBLE_GALAXY_CMD := env_var_or_default("ANSIBLE_GALAXY_CMD", "uvx --from ansible-core ansible-galaxy")
ANSIBLE_PLAYBOOK_CMD := env_var_or_default("ANSIBLE_PLAYBOOK_CMD", "uvx --from ansible-core ansible-playbook")
SOPS_AGE_KEY_FILE := env_var_or_default("SOPS_AGE_KEY_FILE", "~/.config/sops/age/keys.txt")

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

compare-feed *ARGS:
    uv run python manage.py compare_django_chat_sample_feed {{ARGS}}

deploy-bootstrap:
    #!/usr/bin/env bash
    set -euo pipefail
    cd deploy
    mkdir -p .ansible/collections
    {{ANSIBLE_GALAXY_CMD}} collection install -r requirements.yml -p .ansible/collections

deploy-static-check *ARGS:
    uv run python manage.py check_django_chat_static_assets {{ARGS}}

deploy-check: deploy-static-check deploy-bootstrap
    #!/usr/bin/env bash
    set -euo pipefail
    cd deploy
    {{ANSIBLE_PLAYBOOK_CMD}} --syntax-check -i inventory/hosts.yml bootstrap.yml
    {{ANSIBLE_PLAYBOOK_CMD}} --syntax-check -i inventory/hosts.yml deploy.yml

deploy-bootstrap-target TARGET: deploy-bootstrap
    cd deploy && {{ANSIBLE_PLAYBOOK_CMD}} -i inventory/hosts.yml bootstrap.yml -l {{TARGET}}

deploy-staging: deploy-static-check deploy-bootstrap
    cd deploy && SOPS_AGE_KEY_FILE={{SOPS_AGE_KEY_FILE}} {{ANSIBLE_PLAYBOOK_CMD}} -i inventory/hosts.yml deploy.yml -l staging

deploy-production: deploy-static-check deploy-bootstrap
    cd deploy && SOPS_AGE_KEY_FILE={{SOPS_AGE_KEY_FILE}} {{ANSIBLE_PLAYBOOK_CMD}} -i inventory/hosts.yml deploy.yml -l production

test *ARGS:
    uv run pytest {{ARGS}}

runserver *ARGS:
    uv run python manage.py runserver {{ARGS}}
