from django.conf import settings
from django.urls import resolve, reverse


def test_project_uses_django_chat_settings():
    assert settings.WAGTAIL_SITE_NAME == "Django Chat"
    assert settings.ROOT_URLCONF == "config.urls"


def test_wagtail_admin_url_is_mounted():
    assert reverse("wagtailadmin_home") == "/cms/"
    match = resolve("/cms/")
    assert match.url_name == "wagtailadmin_home"


def test_cast_urls_are_mounted():
    assert reverse("cast:styleguide") == "/styleguide/"
