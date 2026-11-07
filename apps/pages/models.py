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
Statik sayfalar (Hakkında, İletişim, vb.) — çok-dilli içerik.

İçerik her dil için ayrı satırda (StaticPageTranslation). Adminde, derginin
desteklediği dillere göre otomatik CKEditor alanları üretilir (bkz. admin.py).
"""
from __future__ import annotations

from django.db import models

from versatileimagefield.fields import VersatileImageField

from apps.core.models import TimeStampedModel


class StaticPage(TimeStampedModel):
    journal = models.ForeignKey(
        "journals.Journal", on_delete=models.CASCADE, related_name="pages",
        null=True, blank=True,
    )
    slug = models.SlugField(max_length=64)
    is_published = models.BooleanField(default=True)
    show_in_menu = models.BooleanField(default=False, help_text="Faz 13 navigasyonu için")
    seq = models.PositiveIntegerField(default=0)
    canonical_url = models.URLField(blank=True, help_text="Boşsa sayfanın kendi adresi kullanılır")
    robots_noindex = models.BooleanField(default=False, help_text="Arama motorlarından gizle (noindex)")
    og_image = VersatileImageField(upload_to="pages/og/", blank=True,
                                   help_text="Sosyal paylaşım görseli (og:image)")

    class Meta:
        unique_together = ("journal", "slug")
        ordering = ["seq", "slug"]
        verbose_name = "Static Page"

    def __str__(self) -> str:
        t = self.tr()
        return t.title if t else self.slug

    def tr(self, locale: str | None = None):
        """İstenen dildeki çeviri; yoksa derginin birincil diline, o da yoksa ilkine düşer."""
        qs = {t.locale: t for t in self.translations.all()}
        if locale and locale in qs:
            return qs[locale]
        if self.journal and self.journal.primary_locale in qs:
            return qs[self.journal.primary_locale]
        return next(iter(qs.values()), None)


class StaticPageTranslation(models.Model):
    page = models.ForeignKey(StaticPage, on_delete=models.CASCADE, related_name="translations")
    locale = models.CharField(max_length=12)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    meta_title = models.CharField(max_length=70, blank=True,
                                  help_text="Boşsa sayfa başlığı kullanılır (max 70)")
    meta_description = models.CharField(max_length=160, blank=True,
                                        help_text="Arama sonucu açıklaması (max 160)")

    class Meta:
        unique_together = ("page", "locale")

    def __str__(self) -> str:
        return f"{self.page.slug} [{self.locale}]"
