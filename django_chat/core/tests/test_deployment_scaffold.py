import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from django_chat.core.staticfiles import minify_css

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_deployment_docs_exist_and_repo_local_ansible_is_gone() -> None:
    for relative_path in [
        "docs/operations-boundary.md",
        "docs/deployment.md",
        "docs/host-review-guide.md",
        "docs/staging-differences.md",
    ]:
        assert (ROOT_DIR / relative_path).is_file(), relative_path

    # ops-control is the only deploy path; a second, repo-local one would drift.
    # Ignored leftovers of the retired workflow (deploy/.ansible, SOPS files) may
    # remain in older checkouts; only the playbooks and their inputs must be gone.
    for retired in [
        "deploy/deploy.yml",
        "deploy/bootstrap.yml",
        "deploy/requirements.yml",
        "deploy/inventory",
        "deploy/group_vars",
    ]:
        assert not (ROOT_DIR / retired).exists(), retired
    assert not (ROOT_DIR / ".sops.yaml").exists()


def test_justfile_deploys_staging_through_ops_control() -> None:
    justfile = (ROOT_DIR / "justfile").read_text()

    assert "deploy-static-check *ARGS:" in justfile
    assert "deploy-production" not in justfile
    assert "ansible-playbook" not in justfile
    recipe = justfile.split("deploy-staging: deploy-static-check", 1)[1].split("\n\n", 1)[0]
    assert 'PROJECTS_ROOT="$(dirname "$source_dir")" just deploy-one django-chat staging' in recipe
    assert '"$(basename "$source_dir")" != "django-chat"' in recipe


def test_staging_secret_defaults_to_ops_control() -> None:
    justfile = (ROOT_DIR / "justfile").read_text()

    assert (
        'DJANGO_CHAT_STAGING_SECRET_FILE := env_var_or_default("DJANGO_CHAT_STAGING_SECRET_FILE", '
        'OPS_CONTROL_DIR / "secrets/staging/django-chat.yml")'
    ) in justfile


def test_old_deploy_secret_paths_stay_gitignored() -> None:
    # Older checkouts may still hold installed collections or SOPS files under
    # the retired deploy/ directory.
    assert "deploy/" in (ROOT_DIR / ".gitignore").read_text().splitlines()


def test_host_review_docs_preserve_staging_boundary() -> None:
    host_review = (ROOT_DIR / "docs/host-review-guide.md").read_text()
    staging_differences = (ROOT_DIR / "docs/staging-differences.md").read_text()
    operations_boundary = (ROOT_DIR / "docs/operations-boundary.md").read_text()

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
    .audio-panel cast-audio-player[data-ready="true"]
      [data-placeholder] {
      opacity: 0;
    }
    """

    assert minify_css(css) == (
        '.audio-panel cast-audio-player[data-ready="true"] [data-placeholder]{opacity:0}'
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


@pytest.mark.parametrize(
    ("disable_cache", "middleware_enabled"),
    [(None, "False"), ("false", "False"), ("true", "True")],
)
def test_production_transcript_cache_middleware_is_opt_in(
    disable_cache: str | None,
    middleware_enabled: str,
) -> None:
    env = {
        "PATH": os.environ["PATH"],
        "DJANGO_READ_DOT_ENV_FILE": "False",
        "DJANGO_" + "SECRET_KEY": "test-value",
        "DJANGO_ALLOWED_HOSTS": "django-chat.example.invalid,localhost",
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_CHAT_MEDIA_STORAGE_BACKEND": "filesystem",
        "DATABASE_URL": "sqlite:///:memory:",
    }
    if disable_cache is not None:
        env["DJANGO_CHAT_DISABLE_TRANSCRIPT_CACHE"] = disable_cache

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from django.conf import settings; "
            "print('django_chat.core.middleware.DisableTranscriptCacheMiddleware' "
            "in settings.MIDDLEWARE)",
        ],
        check=True,
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == middleware_enabled


@pytest.mark.parametrize(
    ("known_speaker_enabled", "expected"),
    [(None, False), ("false", False), ("true", True)],
)
def test_known_speaker_environment_flag_reaches_django_cast(
    monkeypatch: pytest.MonkeyPatch,
    known_speaker_enabled: str | None,
    expected: bool,
) -> None:
    from cast.voxhelm.client import VoxhelmClient

    monkeypatch.setenv("CAST_VOXHELM_API_BASE", "https://voxhelm.example.invalid/api")
    monkeypatch.setenv("CAST_VOXHELM_API_" + "KEY", "test-value")
    monkeypatch.delenv("CAST_VOXHELM_KNOWN_SPEAKER_ENABLED", raising=False)
    if known_speaker_enabled is not None:
        monkeypatch.setenv("CAST_VOXHELM_KNOWN_SPEAKER_ENABLED", known_speaker_enabled)
    assert VoxhelmClient.from_settings().known_speaker_enabled is expected


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


def test_s3_media_storage_configures_public_transcript_storage_alias() -> None:
    env = {
        "PATH": os.environ["PATH"],
        "DJANGO_READ_DOT_ENV_FILE": "False",
        "DJANGO_SECRET_KEY": "production-test-secret",
        "DJANGO_ALLOWED_HOSTS": "django-chat.example.invalid,localhost",
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_CHAT_MEDIA_STORAGE_BACKEND": "s3",
        "DJANGO_CHAT_S3_ACCESS_KEY_ID": "fake-access-key",
        "DJANGO_CHAT_S3_SECRET_ACCESS_KEY": "fake-secret-key",
        "DJANGO_CHAT_S3_STORAGE_BUCKET_NAME": "django-chat-media",
        "DJANGO_CHAT_S3_CUSTOM_DOMAIN": "media.example.invalid",
        "DJANGO_CHAT_MEDIA_URL": "https://media.example.invalid/",
        "DATABASE_URL": "sqlite:///:memory:",
    }

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; "
            "import django; "
            "from django.conf import settings; "
            "from django.core.files.storage import storages; "
            "django.setup(); "
            "from cast.models.contributors import get_voice_reference_storage; "
            "from cast.private_storage import get_transcript_storage; "
            "print(json.dumps({"
            "'default': settings.STORAGES['default'], "
            "'cast_public_transcripts': settings.STORAGES['cast_public_transcripts'], "
            "'cast_voice_references': settings.STORAGES['cast_voice_references'], "
            "'has_cast_private_media': 'cast_private_media' in settings.STORAGES, "
            "'transcript_uses_public_alias': "
            "get_transcript_storage() is storages['cast_public_transcripts'], "
            "'voice_references_use_private_alias': "
            "get_voice_reference_storage() is storages['cast_voice_references'], "
            "}, sort_keys=True)); "
            "print(settings.MEDIA_URL)",
        ],
        check=True,
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    storages = json.loads(result.stdout.splitlines()[0])
    assert storages["default"]["BACKEND"] == "storages.backends.s3.S3Storage"
    assert storages["cast_public_transcripts"]["BACKEND"] == "storages.backends.s3.S3Storage"
    assert storages["cast_voice_references"]["BACKEND"] == "storages.backends.s3.S3Storage"
    assert storages["default"]["OPTIONS"]["bucket_name"] == "django-chat-media"
    assert storages["cast_public_transcripts"]["OPTIONS"]["bucket_name"] == "django-chat-media"
    assert storages["cast_voice_references"]["OPTIONS"]["bucket_name"] == "django-chat-media"
    assert (
        storages["cast_public_transcripts"]["OPTIONS"]["custom_domain"] == "media.example.invalid"
    )
    assert "custom_domain" not in storages["cast_voice_references"]["OPTIONS"]
    assert "location" not in storages["default"]["OPTIONS"]
    assert "location" not in storages["cast_public_transcripts"]["OPTIONS"]
    assert "location" not in storages["cast_voice_references"]["OPTIONS"]
    assert storages["cast_voice_references"]["OPTIONS"]["querystring_auth"] is True
    assert storages["cast_voice_references"]["OPTIONS"]["default_acl"] == "private"
    assert storages["has_cast_private_media"] is False
    assert storages["transcript_uses_public_alias"] is True
    assert storages["voice_references_use_private_alias"] is True
    assert result.stdout.splitlines()[1] == "https://media.example.invalid/"


def test_django_cast_private_media_falls_back_to_non_public_filesystem_storage() -> None:
    from cast.private_storage import get_private_media_storage

    storage = get_private_media_storage()

    assert storage.__class__.__name__ == "PrivateFileSystemStorage"
    with pytest.raises(ValueError, match="not accessible via a URL"):
        storage.url("example.json")


def test_django_cast_public_transcript_artifacts_use_documented_storage_prefix() -> None:
    transcript_model = apps.get_model("cast", "Transcript")

    upload_prefixes = {
        field_name: transcript_model._meta.get_field(field_name).upload_to
        for field_name in ("podlove", "vtt", "dote")
    }

    assert upload_prefixes == {
        "podlove": "cast_transcript/",
        "vtt": "cast_transcript/",
        "dote": "cast_transcript/",
    }


def test_python_version_file_names_the_deployed_python() -> None:
    # ops-control's deploy-django-chat.yml pins the same version and refuses a
    # source whose .python-version differs; change both together.
    assert (ROOT_DIR / ".python-version").read_text().strip() == "3.15.0"
