import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from django_chat.core.staticfiles import minify_css

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_deploy_scaffold_files_exist() -> None:
    required_paths = [
        "deploy/ansible.cfg",
        "deploy/requirements.yml",
        "deploy/inventory/hosts.yml",
        "deploy/group_vars/django_chat.yml",
        "deploy/group_vars/staging.yml",
        "deploy/group_vars/production.yml",
        "deploy/secrets/staging.example.yml",
        "deploy/secrets/production.example.yml",
        "deploy/tasks/bootstrap-host.yml",
        "deploy/bootstrap.yml",
        "deploy/deploy.yml",
        ".sops.yaml",
        "docs/operations-boundary.md",
        "docs/deployment.md",
        "docs/host-review-guide.md",
        "docs/staging-differences.md",
    ]

    for relative_path in required_paths:
        assert (ROOT_DIR / relative_path).is_file(), relative_path


def test_justfile_exposes_deploy_recipes() -> None:
    justfile = (ROOT_DIR / "justfile").read_text()

    for recipe in [
        "deploy-bootstrap:",
        "deploy-bootstrap-target TARGET:",
        "deploy-static-check *ARGS:",
        "deploy-check:",
        "deploy-staging:",
        "deploy-production:",
    ]:
        assert recipe in justfile


def test_ops_library_dependency_is_pinned() -> None:
    requirements = (ROOT_DIR / "deploy/requirements.yml").read_text()

    assert "https://github.com/ephes/ops-library.git" in requirements
    assert "5faa07767dc83aa06501a09d2ed59a199b6d8ed5" in requirements
    for collection, version in [
        ("community.postgresql", "4.2.0"),
        ("community.general", "12.6.0"),
        ("community.sops", "2.3.0"),
        ("ansible.posix", "2.1.0"),
    ]:
        assert collection in requirements
        assert f"version: {version}" in requirements


def test_deploy_playbook_role_sequence_is_explicit() -> None:
    playbook = (ROOT_DIR / "deploy/deploy.yml").read_text()

    uv_index = playbook.index("local.ops_library.uv_install")
    traefik_index = playbook.index("local.ops_library.traefik_deploy")
    wagtail_index = playbook.index("local.ops_library.wagtail_deploy")
    post_tasks_index = playbook.index("post_tasks:")
    restart_index = playbook.index("Deploy | Restart Django Chat application service")

    assert uv_index < traefik_index < wagtail_index < post_tasks_index < restart_index
    assert re.search(r"name:\s*['\"]?\{\{\s*wagtail_systemd_unit_name\s*\}\}['\"]?", playbook)
    assert "state: restarted" in playbook
    group_vars = (ROOT_DIR / "deploy/group_vars/django_chat.yml").read_text()
    assert "wagtail_db_worker_enabled: true" in group_vars
    assert 'wagtail_db_worker_backend: "cast_transcripts"' in group_vars
    assert 'uv_version: "0.11.7"' in group_vars
    assert "wagtail_gunicorn_workers: 3" in group_vars
    assert 'wagtail_traefik_cert_resolver: "letsencrypt"' in group_vars
    assert "Deploy | Restart Django Chat transcript worker service" in playbook
    assert "wagtail_db_worker_unit_name" in playbook


def test_deployment_secret_policy_is_gitignored() -> None:
    gitignore = (ROOT_DIR / ".gitignore").read_text()

    for pattern in [
        "deploy/.ansible/",
        "deploy/secrets/*.sops.yml",
        "deploy/secrets/*.decrypted.yml",
        "!deploy/secrets/*.example.yml",
    ]:
        assert pattern in gitignore

    for secret_example in (ROOT_DIR / "deploy/secrets").glob("*.example.yml"):
        assert "CHANGEME" in secret_example.read_text()


def test_host_review_docs_preserve_staging_boundary() -> None:
    host_review = (ROOT_DIR / "docs/host-review-guide.md").read_text()
    staging_differences = (ROOT_DIR / "docs/staging-differences.md").read_text()
    operations_boundary = (ROOT_DIR / "docs/operations-boundary.md").read_text()
    staging_group_vars = (ROOT_DIR / "deploy/group_vars/staging.yml").read_text()

    assert "Staging is live" in host_review
    assert "https://djangochat.staging.django-cast.com/cms/" in host_review
    assert "Do not commit, document, or print admin passwords" in host_review
    assert "Full-catalog audio is copied to the staging media bucket" in host_review
    assert "The staging feed is not canonical" in staging_differences
    assert "Staging does not mean production migration is complete" in staging_differences
    assert "`cast_transcripts` database worker" in staging_differences
    assert "Wagtail can queue" in staging_differences
    assert "Voxhelm transcript generation" in staging_differences
    assert "reviewers do not need SOPS decrypt access" in operations_boundary
    assert "full-catalog audio served through the public media host" in operations_boundary
    assert "Voxhelm-backed" in operations_boundary
    assert "transcript demo" in operations_boundary
    assert "djangochat.staging.django-cast.com" in staging_group_vars


def test_staging_docs_do_not_carry_obsolete_media_blocker_phrases() -> None:
    relevant_docs = [
        ROOT_DIR / "README.md",
        ROOT_DIR / "docs/host-review-guide.md",
        ROOT_DIR / "docs/staging-differences.md",
        ROOT_DIR / "docs/operations-boundary.md",
        ROOT_DIR / "docs/deployment.md",
        ROOT_DIR / "docs/local-development.md",
    ]
    obsolete_phrases = [
        "audio copy is blocked",
        "media copy is blocked",
        "media copy blocker",
        "verification remains blocked",
        "playback/media verification is pending",
        "playback is currently unavailable",
        "sample audio playback is not available yet",
        "audio remains metadata-only",
        "treat audio playback as pending",
        "s3:putobject is not allowed",
        "or copied staging audio",
    ]
    for doc_path in relevant_docs:
        normalized = " ".join(doc_path.read_text().replace("`", "").split()).lower()
        for phrase in obsolete_phrases:
            assert phrase not in normalized, (
                f"{doc_path.name} still contains obsolete phrase: {phrase!r}"
            )


def test_static_asset_check_passes_for_bundled_source_manifests() -> None:
    call_command("check_django_chat_static_assets")


def test_static_asset_check_fails_when_manifest_is_missing(tmp_path: Path) -> None:
    missing_manifest = tmp_path / "missing" / "manifest.json"

    with (
        override_settings(
            DJANGO_VITE={
                "missing": {
                    "static_url_prefix": "missing/",
                    "manifest_path": missing_manifest,
                },
            },
        ),
        pytest.raises(CommandError, match="Missing required Django Chat source static"),
    ):
        call_command("check_django_chat_static_assets")


def test_css_minifier_preserves_strings_and_required_calc_spacing() -> None:
    css = """
    .example {
      content: "keep   spaces /* and comment markers */";
      width: calc(100% - 1rem);
      color: red;
    }
    .example + .sibling {
      margin-top: 1rem;
    }
    /* remove me */
    """

    assert minify_css(css) == (
        '.example{content:"keep   spaces /* and comment markers */";'
        "width:calc(100% - 1rem);color:red} .example + .sibling{margin-top:1rem}"
    )


def test_css_minifier_preserves_descendant_attribute_selector_spacing() -> None:
    css = """
    .audio-panel podlove-player[data-django-chat-player-ready="true"]
      [data-django-chat-player-placeholder] {
      opacity: 0;
    }
    """

    assert minify_css(css) == (
        '.audio-panel podlove-player[data-django-chat-player-ready="true"] '
        "[data-django-chat-player-placeholder]{opacity:0}"
    )


def test_css_minifier_preserves_descendant_pseudo_and_attribute_spacing() -> None:
    # A space before `:` or `[` in a selector is a descendant combinator;
    # removing it turns e.g. `.filter-form :is(input)` into the compound
    # selector `.filter-form:is(input)` and silently breaks the rule.
    css = """
    .filter-form :is(input, select):focus {
      outline: 2px solid red;
    }
    html.js-reveal [data-reveal] {
      opacity: 0;
    }
    """

    assert minify_css(css) == (
        ".filter-form :is(input,select):focus{outline:2px solid red} "
        "html.js-reveal [data-reveal]{opacity:0}"
    )


def test_collectstatic_minifies_project_css_before_manifest_hashing(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    static_root = tmp_path / "staticfiles"
    css_path = source_root / "django_chat" / "css" / "site.css"
    image_path = source_root / "django_chat" / "img" / "paper.png"
    css_path.parent.mkdir(parents=True)
    image_path.parent.mkdir(parents=True)
    css_path.write_text(
        """
        .hero {
          background: url("../img/paper.png");
          content: "keep   spacing";
        }
        /* deployment-only comment */
        """,
        encoding="utf-8",
    )
    image_path.write_bytes(b"fake-png")

    with override_settings(
        STATICFILES_DIRS=[source_root],
        STATIC_ROOT=static_root,
        STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {
                "BACKEND": (
                    "django_chat.core.staticfiles.MinifiedCompressedManifestStaticFilesStorage"
                ),
            },
        },
    ):
        call_command("collectstatic", interactive=False, verbosity=0)

    manifest = json.loads((static_root / "staticfiles.json").read_text(encoding="utf-8"))
    hashed_css_name = manifest["paths"]["django_chat/css/site.css"]
    hashed_image_name = manifest["paths"]["django_chat/img/paper.png"]

    collected_css = (static_root / "django_chat" / "css" / "site.css").read_text(
        encoding="utf-8",
    )
    hashed_css = (static_root / hashed_css_name).read_text(encoding="utf-8")

    assert collected_css == '.hero{background:url("../img/paper.png");content:"keep   spacing"}'
    assert "deployment-only comment" not in hashed_css
    assert "keep   spacing" in hashed_css
    assert f'url("../img/{Path(hashed_image_name).name}")' in hashed_css
    assert "  " not in hashed_css.replace("keep   spacing", "")


def test_collectstatic_reminifies_from_source_over_stale_collected_copy(tmp_path: Path) -> None:
    # The minifier rewrites the collected copy in place, so a later
    # collectstatic run must not trust it: when the source is unchanged,
    # collectstatic skips the copy step and post-processing would otherwise
    # re-minify stale (e.g. produced by an older, buggier minifier) output
    # forever. Minification has to restart from the pristine source.
    source_root = tmp_path / "source"
    static_root = tmp_path / "staticfiles"
    css_path = source_root / "django_chat" / "css" / "site.css"
    css_path.parent.mkdir(parents=True)
    css_path.write_text(".hero {\n  color: red;\n}\n", encoding="utf-8")

    storages = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": (
                "django_chat.core.staticfiles.MinifiedCompressedManifestStaticFilesStorage"
            ),
        },
    }
    with override_settings(
        STATICFILES_DIRS=[source_root],
        STATIC_ROOT=static_root,
        STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
        STORAGES=storages,
    ):
        call_command("collectstatic", interactive=False, verbosity=0)

        collected_css_path = static_root / "django_chat" / "css" / "site.css"
        collected_css_path.write_text(".hero{color:stale}", encoding="utf-8")

        call_command("collectstatic", interactive=False, verbosity=0)

    manifest = json.loads((static_root / "staticfiles.json").read_text(encoding="utf-8"))
    hashed_css_name = manifest["paths"]["django_chat/css/site.css"]
    assert collected_css_path.read_text(encoding="utf-8") == ".hero{color:red}"
    assert (static_root / hashed_css_name).read_text(encoding="utf-8") == ".hero{color:red}"


def test_collectstatic_minification_does_not_mutate_source_when_linking(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    static_root = tmp_path / "staticfiles"
    css_path = source_root / "django_chat" / "css" / "site.css"
    css_path.parent.mkdir(parents=True)
    source_css = """
    .hero {
      color: red;
    }
    /* source comment */
    """
    css_path.write_text(source_css, encoding="utf-8")

    with override_settings(
        STATICFILES_DIRS=[source_root],
        STATIC_ROOT=static_root,
        STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {
                "BACKEND": (
                    "django_chat.core.staticfiles.MinifiedCompressedManifestStaticFilesStorage"
                ),
            },
        },
    ):
        call_command("collectstatic", interactive=False, verbosity=0, link=True)

    collected_css_path = static_root / "django_chat" / "css" / "site.css"

    assert css_path.read_text(encoding="utf-8") == source_css
    assert not collected_css_path.is_symlink()
    assert collected_css_path.read_text(encoding="utf-8") == ".hero{color:red}"


def test_production_settings_import_with_explicit_environment() -> None:
    env = {
        "PATH": os.environ["PATH"],
        "DJANGO_READ_DOT_ENV_FILE": "False",
        "DJANGO_SECRET_KEY": "production-test-secret",
        "DJANGO_ALLOWED_HOSTS": "django-chat.example.invalid,localhost",
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_CHAT_MEDIA_STORAGE_BACKEND": "filesystem",
        "DATABASE_URL": "sqlite:///:memory:",
    }

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from django.conf import settings; "
            "print(settings.SECRET_KEY); "
            "print(settings.ALLOWED_HOSTS[0]); "
            "print(settings.WAGTAILADMIN_BASE_URL)",
        ],
        check=True,
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == [
        "production-test-secret",
        "django-chat.example.invalid",
        "https://django-chat.example.invalid/cms/",
    ]


def test_production_settings_import_with_empty_allowed_hosts_and_explicit_admin_url() -> None:
    env = {
        "PATH": os.environ["PATH"],
        "DJANGO_READ_DOT_ENV_FILE": "False",
        "DJANGO_SECRET_KEY": "production-test-secret",
        "DJANGO_ALLOWED_HOSTS": "",
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_CHAT_MEDIA_STORAGE_BACKEND": "filesystem",
        "DJANGO_CHAT_WAGTAIL_ADMIN_BASE_URL": "https://admin.example.invalid/cms/",
        "DATABASE_URL": "sqlite:///:memory:",
    }

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from django.conf import settings; "
            "print(settings.ALLOWED_HOSTS); "
            "print(settings.WAGTAILADMIN_BASE_URL)",
        ],
        check=True,
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == [
        "[]",
        "https://admin.example.invalid/cms/",
    ]
