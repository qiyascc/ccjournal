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

"""Duyurular (OJS Announcements) — çok-dilli, yayın + son-tarih."""
from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Announcement(TimeStampedModel):
    journal = models.ForeignKey("journals.Journal", on_delete=models.CASCADE,
                                related_name="announcements", null=True, blank=True)
    date_posted = models.DateField(default=timezone.localdate)
    date_expire = models.DateField(null=True, blank=True,
                                   help_text="Boşsa süresiz görünür")
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["-date_posted"]
        verbose_name = "Announcement"

    def __str__(self) -> str:
        t = self.tr()
        return t.title if t else f"Announcement #{self.pk}"

    def tr(self, locale: str | None = None):
        qs = {t.locale: t for t in self.translations.all()}
        if locale and locale in qs:
            return qs[locale]
        if self.journal and self.journal.primary_locale in qs:
            return qs[self.journal.primary_locale]
        return next(iter(qs.values()), None)

    @property
    def is_active(self) -> bool:
        return self.is_published and (
            self.date_expire is None or self.date_expire >= timezone.localdate())


class AnnouncementTranslation(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE,
                                     related_name="translations")
    locale = models.CharField(max_length=12)
    title = models.CharField(max_length=255)
    short_description = models.TextField(blank=True)
    body = models.TextField(blank=True)

    class Meta:
        unique_together = ("announcement", "locale")

    def __str__(self) -> str:
        return f"{self.title} [{self.locale}]"
