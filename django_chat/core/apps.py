from django.apps import AppConfig

PODCAST_ADMIN_DEFAULT_ORDERING = "-post__visible_date"


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_chat.core"

    def ready(self) -> None:
        from cast.models import Podcast
        from django_comments.signals import comment_will_be_posted

        from .receivers import reject_comment_when_disabled

        # Wagtail's Page explorer defaults to "most recently updated", which is
        # awkward for imported podcast catalogs. Match the public episode index
        # by showing the newest published episode first under the Podcast page.
        Podcast.admin_default_ordering = PODCAST_ADMIN_DEFAULT_ORDERING

        # Enforce the comments-enabled gate server-side. The episode template
        # only hides the comment UI when comments are off; the no-JS and AJAX
        # post views would otherwise accept a direct POST.
        comment_will_be_posted.connect(
            reject_comment_when_disabled,
            dispatch_uid="django_chat_reject_comment_when_disabled",
        )
