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
Değerlendirme (peer review) + editöryal kararlar.

Akış: Submission -> ReviewRound(lar) -> her round'da ReviewAssignment(lar) ->
editör EditorialDecision verir (kabul / revizyon / red / sonraki aşama...).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.submissions.models import Stage


class ReviewMode(models.TextChoices):
    OPEN = "open", "Open"
    SINGLE_ANONYMOUS = "single_anonymous", "Single-anonymous"
    DOUBLE_ANONYMOUS = "double_anonymous", "Double-anonymous"


class StageAssignment(models.Model):
    """Bir gönderiyi yöneten editör/yardımcı ataması."""

    submission = models.ForeignKey(
        "submissions.Submission", on_delete=models.CASCADE, related_name="stage_assignments"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20)
    can_change_metadata = models.BooleanField(default=True)
    is_recommend_only = models.BooleanField(default=False)

    class Meta:
        unique_together = ("submission", "user", "role")


class ReviewRound(models.Model):
    submission = models.ForeignKey(
        "submissions.Submission", on_delete=models.CASCADE, related_name="review_rounds"
    )
    stage = models.IntegerField(choices=Stage.choices, default=Stage.REVIEW)
    round = models.PositiveIntegerField(default=1)

    class Status(models.IntegerChoices):
        PENDING = 1, "Awaiting reviewers"
        IN_REVIEW = 2, "In review"
        REVISIONS = 3, "Revisions requested"
        RESUBMITTED = 4, "Resubmitted"
        ACCEPTED = 5, "Accept"
        DECLINED = 6, "Decline"

    status = models.IntegerField(choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("submission", "stage", "round")
        ordering = ["round"]

    def __str__(self) -> str:
        return f"{self.submission} · Round {self.round}"


def _review_token():
    import secrets
    return secrets.token_urlsafe(32)


class ReviewAssignment(models.Model):
    review_round = models.ForeignKey(
        ReviewRound, on_delete=models.CASCADE, related_name="assignments"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_assignments"
    )
    review_mode = models.CharField(
        max_length=20, choices=ReviewMode.choices, default=ReviewMode.DOUBLE_ANONYMOUS
    )

    access_token = models.CharField(max_length=64, unique=True, db_index=True,
                                    default=_review_token, editable=False)
    date_assigned = models.DateTimeField(auto_now_add=True)
    date_confirmed = models.DateTimeField(null=True, blank=True)
    date_due = models.DateField(null=True, blank=True)
    date_completed = models.DateTimeField(null=True, blank=True)
    date_reminded = models.DateTimeField(null=True, blank=True)
    declined = models.BooleanField(default=False)

    class Recommendation(models.IntegerChoices):
        ACCEPT = 1, "Accept"
        MINOR_REVISIONS = 2, "Minor revisions"
        MAJOR_REVISIONS = 3, "Major revisions"
        RESUBMIT_HERE = 4, "Resubmit (this journal)"
        RESUBMIT_ELSEWHERE = 5, "Resubmit elsewhere"
        DECLINE = 6, "Decline"
        SEE_COMMENTS = 7, "See comments"

    recommendation = models.IntegerField(
        choices=Recommendation.choices, null=True, blank=True
    )
    comments_for_editor = models.TextField(blank=True)
    comments_for_author = models.TextField(blank=True)
    competing_interests = models.TextField(blank=True)
    quality = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Editor rating 1-5")
    form_responses = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = ("review_round", "reviewer")

    def __str__(self) -> str:
        return f"{self.reviewer} · {self.review_round}"

    @property
    def is_complete(self) -> bool:
        return self.date_completed is not None


class EditorialDecision(models.Model):
    submission = models.ForeignKey(
        "submissions.Submission", on_delete=models.CASCADE, related_name="decisions"
    )
    review_round = models.ForeignKey(
        ReviewRound, null=True, blank=True, on_delete=models.SET_NULL, related_name="decisions"
    )
    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    stage = models.IntegerField(choices=Stage.choices)

    class Decision(models.IntegerChoices):
        ACCEPT = 1, "Accept"
        DECLINE = 4, "Decline"
        SEND_TO_REVIEW = 8, "Send to review"
        PENDING_REVISIONS = 9, "Request revisions"
        RESUBMIT = 10, "Resubmit"
        SEND_TO_PRODUCTION = 11, "Send to production"
        SEND_TO_COPYEDIT = 12, "Send to copyediting"
        INITIAL_DECLINE = 13, "Desk reject (pre-review)"

    decision = models.IntegerField(choices=Decision.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Editorial Decision"
        verbose_name_plural = "Editorial Decisions"

    def __str__(self) -> str:
        return f"{self.get_decision_display()} · {self.submission}"


class Discussion(models.Model):
    """Aşama içi tartışma (OJS 'query'). Editör-yazar-hakem mesajlaşması."""

    submission = models.ForeignKey(
        "submissions.Submission", on_delete=models.CASCADE, related_name="discussions"
    )
    stage = models.IntegerField(choices=Stage.choices)
    subject = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class DiscussionMessage(models.Model):
    discussion = models.ForeignKey(
        Discussion, on_delete=models.CASCADE, related_name="messages"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class ReviewFormTemplate(models.Model):
    """Özelleştirilebilir hakem değerlendirme formu (OJS review forms).

    Aktif şablon (journal başına ilk `is_active`) yeni değerlendirmelerin public
    formuna eklenir. Yanıtlar şablona referansla DEĞİL, snapshot olarak
    ReviewAssignment.form_responses içinde saklanır.
    """
    journal = models.ForeignKey("journals.Journal", on_delete=models.CASCADE,
                                related_name="review_form_templates")
    title = models.CharField(max_length=160, default="Review form")
    description = models.TextField(blank=True, help_text="Hakeme formun üstünde gösterilir")
    is_active = models.BooleanField(default=False, db_index=True,
                                    help_text="Aktif şablon yeni değerlendirmelerde kullanılır")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_active", "-created_at"]
        verbose_name = "Review form"
        verbose_name_plural = "Review forms"

    def __str__(self) -> str:
        return f"{self.title}{' · active' if self.is_active else ''}"

    @classmethod
    def active_for(cls, journal):
        return cls.objects.filter(journal=journal, is_active=True).first()


class ReviewFormItem(models.Model):
    """Review formundaki tek soru."""

    class Kind(models.TextChoices):
        TEXT = "text", "Single-line text"
        TEXTAREA = "textarea", "Multi-line text"
        RADIO = "radio", "Single choice (radio)"
        CHECKBOXES = "checkboxes", "Multiple choice (checkboxes)"
        DROPDOWN = "dropdown", "Dropdown"

    template = models.ForeignKey(ReviewFormTemplate, on_delete=models.CASCADE,
                                 related_name="items")
    seq = models.FloatField(default=1.0)
    label = models.CharField(max_length=500)
    help_text = models.CharField(max_length=500, blank=True)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.TEXTAREA)
    choices = models.JSONField(default=list, blank=True,
                               help_text='Seçenek listesi (radio/checkboxes/dropdown), ör. ["Yes", "No"]')
    required = models.BooleanField(default=False)

    class Meta:
        ordering = ["seq", "id"]
        verbose_name = "Review form item"

    def __str__(self) -> str:
        return self.label[:60]


class ReviewInterest(models.Model):
    """Hakem ilgi alanı (kontrollü kelime dağarcığı)."""
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Review interest"

    def __str__(self) -> str:
        return self.name


class ReviewerProfile(models.Model):
    """Hakem havuzu profili — ilgi alanları, uzmanlık, uygunluk."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviewer_profile")
    interests = models.ManyToManyField(ReviewInterest, blank=True, related_name="reviewers")
    affiliation = models.CharField(max_length=255, blank=True)
    expertise = models.TextField(blank=True, help_text="Serbest metin uzmanlık özeti")
    is_available = models.BooleanField(default=True, db_index=True)
    public_listing = models.BooleanField(
        default=False, db_index=True,
        help_text="Hakem, /reviewers/ teşekkür sayfasında listelenmeyi kabul etti")
    unavailable_until = models.DateField(
        null=True, blank=True,
        help_text="Tatil modu: bu tarihe kadar yeni davet önerilmez")
    max_per_year = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Yıllık kabul edilen azami değerlendirme")

    class Meta:
        verbose_name = "Reviewer profile"

    def __str__(self) -> str:
        return f"{self.user} (reviewer)"

    @property
    def avg_days(self):
        """Tamamlanan değerlendirmeler için ortalama gün."""
        comp = [a for a in self.user.review_assignments.all() if a.date_completed]
        if not comp:
            return None
        days = [(a.date_completed - a.date_assigned).days for a in comp]
        return round(sum(days) / len(days), 1)


class Appeal(models.Model):
    """Ret kararına resmi itiraz (COPE temyiz süreci).

    Yazar, çalışma alanından bir kez itiraz açar; editoryal ekip admin'den
    inceleyip sonuçlandırır. Tüm süreç kayıt altındadır."""

    class Status(models.IntegerChoices):
        OPEN = 1, "Open"
        UPHELD = 2, "Decision upheld"
        OVERTURNED = 3, "Decision overturned (re-review)"

    submission = models.OneToOneField(
        "submissions.Submission", on_delete=models.CASCADE, related_name="appeal")
    reason = models.TextField(help_text="Yazarın itiraz gerekçesi")
    status = models.IntegerField(choices=Status.choices, default=Status.OPEN,
                                 db_index=True)
    decision_note = models.TextField(blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Appeal"

    def __str__(self) -> str:
        return f"Appeal · submission #{self.submission_id} · {self.get_status_display()}"


class BoardPresence(models.Model):
    """Editöryal board'da kim aktif — poll-tabanlı presence (websocket'siz)."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="board_presence")
    last_seen = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "Board presence"

    def __str__(self) -> str:
        return f"{self.user} @ {self.last_seen:%H:%M:%S}"
