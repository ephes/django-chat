# Local commands for the Django Chat scaffold.

ANSIBLE_GALAXY_CMD := env_var_or_default("ANSIBLE_GALAXY_CMD", "uvx --from ansible-core ansible-galaxy")
ANSIBLE_PLAYBOOK_CMD := env_var_or_default("ANSIBLE_PLAYBOOK_CMD", "uvx --from ansible-core ansible-playbook")
SOPS_AGE_KEY_FILE := env_var_or_default("SOPS_AGE_KEY_FILE", "~/.config/sops/age/keys.txt")
DJANGO_CHAT_STAGING_SECRET_FILE := env_var_or_default("DJANGO_CHAT_STAGING_SECRET_FILE", "deploy/secrets/staging.sops.yml")

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

dev *ARGS:
    just runserver-staging-media {{ARGS}}

runserver *ARGS:
    just dev {{ARGS}}

runserver-local-media *ARGS:
    uv run python manage.py runserver {{ARGS}}

runserver-staging-media *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail

    secret_file="{{DJANGO_CHAT_STAGING_SECRET_FILE}}"
    if [[ ! -f "$secret_file" ]]; then
        echo "Missing staging secret file: $secret_file" >&2
        exit 1
    fi
    command -v sops >/dev/null || {
        echo "Missing required command: sops" >&2
        exit 1
    }
    command -v yq >/dev/null || {
        echo "Missing required command: yq" >&2
        exit 1
    }

    require_secret() {
        local key="$1"
        local value
        value="$(printf '%s' "$secrets" | yq -r ".${key} // \"\"")"
        if [[ -z "$value" || "$value" == "null" ]]; then
            echo "Missing required key '${key}' in $secret_file" >&2
            exit 1
        fi
        printf '%s' "$value"
    }

    secrets="$(SOPS_AGE_KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}" sops --decrypt "$secret_file")"
    cloudfront_domain="$(require_secret cloudfront_domain)"

    export DJANGO_CHAT_MEDIA_STORAGE_BACKEND=s3
    export DJANGO_CHAT_S3_ACCESS_KEY_ID="$(require_secret django_aws_access_key_id)"
    export DJANGO_CHAT_S3_SECRET_ACCESS_KEY="$(require_secret django_aws_secret_access_key)"
    export DJANGO_CHAT_S3_STORAGE_BUCKET_NAME="$(require_secret django_aws_storage_bucket_name)"
    export DJANGO_CHAT_S3_CUSTOM_DOMAIN="$cloudfront_domain"
    export DJANGO_CHAT_MEDIA_URL="https://${cloudfront_domain}/"

    uv run python manage.py runserver {{ARGS}}
