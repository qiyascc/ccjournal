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
İletişim modelleri: e-posta şablonları (çok-dilli, dergiye özel + global varsayılan)
ve uygulama-içi bildirimler.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models


class EmailTemplate(models.Model):
    """
    (journal, key, locale) bazlı şablon. journal=None -> global varsayılan.
    MailService önce dergiye özel, yoksa global; istenen locale yoksa 'en'e düşer.
    """

    KEY_CHOICES = [
        ("submission_ack", "Submission acknowledgement (author)"),
        ("editor_new_submission", "New submission (editor)"),
        ("review_request", "Review request (reviewer)"),
        ("review_reminder", "Review reminder (reviewer)"),
        ("decision_accept", "Decision: accept (author)"),
        ("decision_decline", "Decision: decline (author)"),
        ("decision_revisions", "Decision: revisions requested (author)"),
        ("publication_published", "Article published (author)"),
        ("issue_published", "New issue published (readers)"),
        ("user_invitation", "Role invitation (invitee)"),
        ("email_verification", "Email verification (new account)"),
    ]

    journal = models.ForeignKey(
        "journals.Journal", null=True, blank=True,
        on_delete=models.CASCADE, related_name="email_templates",
    )
    key = models.CharField(max_length=64, choices=KEY_CHOICES)
    locale = models.CharField(max_length=14, default="en")
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="Django template söz dizimi: {{ author }}, {{ title }} ...")
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("journal", "key", "locale")
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"

    def __str__(self) -> str:
        scope = self.journal.path if self.journal_id else "global"
        return f"{self.key} [{self.locale}] ({scope})"


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    journal = models.ForeignKey(
        "journals.Journal", null=True, blank=True, on_delete=models.CASCADE
    )
    type = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=512, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self) -> str:
        return f"{self.recipient} · {self.title}"


class NewsletterSubscriber(models.Model):
    """Hesapsız bülten aboneliği (double opt-in).

    Okuyucu yalnız e-posta bırakır; onay linkine tıklayınca aktifleşir.
    Yeni sayı duyuruları hem opt-in kullanıcılara hem buradaki onaylı
    abonelere gider (yinelenen adresler tekilleştirilir)."""
    email = models.EmailField(unique=True)
    confirmed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Newsletter subscriber"

    def __str__(self) -> str:
        state = "confirmed" if self.confirmed_at else "pending"
        return f"{self.email} ({state})"


class EmailLog(models.Model):
    """Gönderilen e-postaların kaydı (OJS submission email log)."""
    SENT = "sent"
    FAILED = "failed"
    STATUS_CHOICES = [(SENT, "Sent"), (FAILED, "Failed")]

    journal = models.ForeignKey("journals.Journal", null=True, blank=True,
                                on_delete=models.SET_NULL)
    template_key = models.CharField(max_length=64, blank=True)
    locale = models.CharField(max_length=14, blank=True)
    from_email = models.CharField(max_length=255, blank=True)
    to_emails = models.TextField(help_text="Virgülle ayrılmış alıcılar")
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=SENT, db_index=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    content_type = models.ForeignKey("contenttypes.ContentType", null=True, blank=True,
                                     on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Email log"
        verbose_name_plural = "Email log"
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self) -> str:
        return f"{self.subject} → {self.to_emails[:60]}"
