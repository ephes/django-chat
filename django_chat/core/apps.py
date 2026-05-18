from django.apps import AppConfig

PODCAST_ADMIN_DEFAULT_ORDERING = "-post__visible_date"


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_chat.core"

    def ready(self) -> None:
        from cast.models import Podcast

        # Wagtail's Page explorer defaults to "most recently updated", which is
        # awkward for imported podcast catalogs. Match the public episode index
        # by showing the newest published episode first under the Podcast page.
        Podcast.admin_default_ordering = PODCAST_ADMIN_DEFAULT_ORDERING
