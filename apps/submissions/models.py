# ==========================================================
#
# █▀█ █ █▄█ ▄▀█ █▀  █▀▀ █▀▀
# ▀▀█ █ ░█░ █▀█ ▄█  █▄▄ █▄▄
#
# Project     : CC Journal
# Developed by: Qiyas CC
# Copyright © 2026 Qiyas CC
# All Rights Reserved.
# ==========================================================

"""
Gönderi (Submission) katmanı = editöryal akış konteyneri.

Önemli kavramsal ayrım (OJS'ten devraldığımız doğru tasarım):
  * Submission  -> bir eserin akıştaki hali (durum, aşama, dosyalar, kararlar)
  * Publication -> o eserin YAYINLANABİLİR, SÜRÜMLENMİŞ metadata'sı (apps.publications)
Bir Submission'ın birden çok Publication (versiyon) çocuğu olabilir; "current"
olan biri vitrinde gösterilir.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel


class Stage(models.IntegerChoices):
    SUBMISSION = 1, "Submission"
    REVIEW = 3, "Review"
    EDITING = 4, "Editing (Copyedit)"
    PRODUCTION = 5, "Production"


class SubmissionStatus(models.IntegerChoices):
    INCOMPLETE = 0, "Incomplete (draft)"
    QUEUED = 1, "Queued"
    PUBLISHED = 3, "Published"
    DECLINED = 4, "Declined"
    SCHEDULED = 5, "Scheduled"


def _author_token():
    import secrets
    return secrets.token_urlsafe(32)


class Submission(TimeStampedModel, SoftDeleteModel):
    journal = models.ForeignKey(
        "journals.Journal", on_delete=models.CASCADE, related_name="submissions"
    )
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="submitted_works",
    )
    locale = models.CharField(max_length=14, default="az")
    categories = models.ManyToManyField(
        "journals.Category", blank=True, related_name="submissions")

    stage = models.IntegerField(choices=Stage.choices, default=Stage.SUBMISSION, db_index=True)
    status = models.IntegerField(
        choices=SubmissionStatus.choices, default=SubmissionStatus.INCOMPLETE, db_index=True
    )
    author_token = models.CharField(max_length=64, unique=True, db_index=True,
                                    default=_author_token, editable=False)
    date_submitted = models.DateTimeField(null=True, blank=True)
    date_status_modified = models.DateTimeField(auto_now=True)
    suggested_reviewers = models.JSONField(default=list, blank=True)
    integrity_report = models.JSONField(default=dict, blank=True)
    integrity_checked_at = models.DateTimeField(null=True, blank=True)

    current_publication = models.ForeignKey(
        "publications.Publication", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        verbose_name = "Submission"
        verbose_name_plural = "Submissions"
        indexes = [models.Index(fields=["journal", "stage", "status"])]

    def __str__(self) -> str:
        pub = self.current_publication
        title = pub.tr_value("title") if pub else "(untitled)"
        return f"#{self.pk} · {title}"

    @property
    def is_published(self) -> bool:
        return self.status == SubmissionStatus.PUBLISHED


class Genre(models.Model):
    """Dosya türü: 'Article Text', 'Data Set', 'Figure', 'Supplementary'..."""

    journal = models.ForeignKey(
        "journals.Journal", on_delete=models.CASCADE, related_name="genres"
    )
    key = models.SlugField(max_length=64)
    name = models.CharField(max_length=120)
    is_supplementary = models.BooleanField(default=False)
    is_dependent = models.BooleanField(
        default=False, help_text="e.g. images embedded in HTML"
    )
    seq = models.FloatField(default=1.0)

    class Meta:
        unique_together = ("journal", "key")
        ordering = ["seq"]

    def __str__(self) -> str:
        return self.name


class FileStage(models.IntegerChoices):
    SUBMISSION = 2, "Submission file"
    REVIEW_FILE = 4, "Sent for review"
    REVIEW_ATTACHMENT = 5, "Reviewer attachment"
    REVIEW_REVISION = 15, "Author revision"
    COPYEDIT = 9, "Copyedit file"
    PROOF = 10, "Proof"
    PRODUCTION_READY = 11, "Production ready"
    DEPENDENT = 17, "Dependent file"
    QUERY = 18, "Discussion attachment"


class SubmissionFile(TimeStampedModel):
    """
    Akış boyunca dosyaları izler. `file_stage` ilerledikçe değişir; `source_file`
    bir önceki sürüme zincir kurar (OJS'teki source_submission_file_id mantığı).
    """

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to="submissions/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    mimetype = models.CharField(max_length=120, blank=True)
    file_size = models.BigIntegerField(default=0)

    file_stage = models.IntegerField(choices=FileStage.choices, db_index=True)
    genre = models.ForeignKey(Genre, null=True, blank=True, on_delete=models.SET_NULL)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    source_file = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="revisions"
    )
    seq = models.FloatField(default=1.0)

    class Meta:
        ordering = ["seq", "created_at"]
        verbose_name = "Submission File"
        verbose_name_plural = "Submission Files"

    def __str__(self) -> str:
        return self.original_filename
