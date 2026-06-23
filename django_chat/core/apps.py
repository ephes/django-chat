from django.apps import AppConfig

PODCAST_ADMIN_DEFAULT_ORDERING = "-post__visible_date"


def _panel_targets_field(panel: object, field_name: str) -> bool:
    return getattr(panel, "field_name", None) == field_name


def _ensure_episode_comments_panel() -> None:
    from cast.models import Episode
    from wagtail.admin.panels import FieldPanel

    if any(_panel_targets_field(panel, "comments_enabled") for panel in Episode.content_panels):
        return

    visible_date_index = next(
        (
            index
            for index, panel in enumerate(Episode.content_panels)
            if _panel_targets_field(panel, "visible_date")
        ),
        -1,
    )
    insert_at = visible_date_index + 1 if visible_date_index >= 0 else len(Episode.content_panels)
    Episode.content_panels = [
        *Episode.content_panels[:insert_at],
        FieldPanel("comments_enabled"),
        *Episode.content_panels[insert_at:],
    ]


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
        _ensure_episode_comments_panel()

        # Enforce the comments-enabled gate server-side. The episode template
        # only hides the comment UI when comments are off; the no-JS and AJAX
        # post views would otherwise accept a direct POST.
        comment_will_be_posted.connect(
            reject_comment_when_disabled,
            dispatch_uid="django_chat_reject_comment_when_disabled",
        )
