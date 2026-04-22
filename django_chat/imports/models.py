from typing import ClassVar

from django.db import models
from django.db.models import Q


class PodcastSourceMetadata(models.Model):
    objects: ClassVar[models.Manager[PodcastSourceMetadata]]

    podcast = models.OneToOneField(
        "cast.Podcast",
        on_delete=models.CASCADE,
        related_name="django_chat_source_metadata",
    )
    simplecast_podcast_id = models.CharField(max_length=64, unique=True)
    rss_feed_url = models.URLField(max_length=1000)
    simplecast_source_url = models.URLField(max_length=1000)
    site_source_url = models.URLField(max_length=1000, blank=True)
    website_url = models.URLField(max_length=1000, blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    source_title = models.CharField(max_length=255)
    source_description = models.TextField(blank=True)
    source_is_explicit = models.BooleanField(null=True, blank=True)
    source_episode_count = models.PositiveIntegerField(null=True, blank=True)
    source_published_at = models.DateTimeField(null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    first_imported_at = models.DateTimeField(auto_now_add=True)
    last_imported_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_title"]

    def __str__(self) -> str:
        return f"{self.source_title} ({self.simplecast_podcast_id})"


class EpisodeSourceMetadata(models.Model):
    objects: ClassVar[models.Manager[EpisodeSourceMetadata]]

    episode = models.OneToOneField(
        "cast.Episode",
        on_delete=models.CASCADE,
        related_name="django_chat_source_metadata",
    )
    matching_key = models.CharField(max_length=512, unique=True)
    rss_guid = models.CharField(max_length=255, blank=True)
    simplecast_episode_id = models.CharField(max_length=64, blank=True)
    simplecast_slug = models.SlugField(max_length=255, blank=True)
    episode_number = models.PositiveIntegerField(null=True, blank=True)
    source_title = models.CharField(max_length=255)
    rss_source_url = models.URLField(max_length=1000, blank=True)
    simplecast_source_url = models.URLField(max_length=1000, blank=True)
    simplecast_api_url = models.URLField(max_length=1000, blank=True)
    simplecast_episode_url = models.URLField(max_length=1000, blank=True)
    original_rss_enclosure_url = models.URLField(max_length=1000, blank=True)
    simplecast_enclosure_url = models.URLField(max_length=1000, blank=True)
    simplecast_audio_file_url = models.URLField(max_length=1000, blank=True)
    audio_file_size = models.PositiveBigIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    rss_description_html = models.TextField(blank=True)
    rss_content_html = models.TextField(blank=True)
    rss_is_explicit = models.BooleanField(null=True, blank=True)
    simplecast_description = models.TextField(blank=True)
    simplecast_long_description_html = models.TextField(blank=True)
    simplecast_transcript_html = models.TextField(blank=True)
    simplecast_is_explicit = models.BooleanField(null=True, blank=True)
    source_published_at = models.DateTimeField(null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    first_imported_at = models.DateTimeField(auto_now_add=True)
    last_imported_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-source_published_at", "-episode_number", "source_title"]
        constraints = [
            models.UniqueConstraint(
                fields=["rss_guid"],
                condition=~Q(rss_guid=""),
                name="imports_unique_episode_rss_guid",
            ),
            models.UniqueConstraint(
                fields=["simplecast_episode_id"],
                condition=~Q(simplecast_episode_id=""),
                name="imports_unique_simplecast_episode_id",
            ),
            models.UniqueConstraint(
                fields=["simplecast_slug"],
                condition=~Q(simplecast_slug=""),
                name="imports_unique_simplecast_slug",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_title} ({self.matching_key})"
