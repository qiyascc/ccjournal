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
Çekirdek soyut modeller.

Tasarım notu (OJS'ten ayrıldığımız nokta):
OJS, her varlık için ``*_settings`` (entity_id, locale, setting_name, setting_value)
biçiminde EAV tabloları kullanır. Esnek ama: tip güvenliği yok, JOIN cehennemi,
indeksleme zayıf, raporlama acı verici. Biz bunun yerine:
  * Çekirdek/sayısal alanlar  -> tipli kolonlar
  * Çevrilebilir metin alanları -> her model için temiz bir `*Translation` çocuk tablosu
    (parler tarzı, ama metaclass büyüsü olmadan; açık ve sorgulanabilir)
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """created_at / updated_at taşıyan taban model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        get_latest_by = "created_at"


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        return super().update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()


class SoftDeleteModel(models.Model):
    """
    Kayıtları fiziksel silmek yerine işaretler. OAI-PMH "tombstone" mantığı için
    (silinen makalenin metaverisini koruma) kritik.
    """

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class TranslatableMixin:
    """
    Çeviri çocuk tablosu olan modeller için yardımcılar.

    Beklenti: ilgili modelin ``translations`` adında bir reverse FK'i ve
    her çeviri satırında ``locale`` alanı vardır. Ayrıca model üzerinde
    ``primary_locale`` alanı bulunur (fallback için).

    Kullanım:
        journal.tr("az").title
        journal.tr().title          # primary_locale'e düşer
    """

    def tr(self, locale: str | None = None):
        locale = locale or getattr(self, "primary_locale", None) or settings.LANGUAGE_CODE
        cache = self.__dict__.setdefault("_tr_cache", {})
        if locale in cache:
            return cache[locale]
        qs = self.translations.all()
        row = next((t for t in qs if t.locale == locale), None)
        if row is None:
            primary = getattr(self, "primary_locale", None)
            row = next((t for t in qs if t.locale == primary), None) or (qs[0] if qs else None)
        cache[locale] = row
        return row

    def tr_value(self, field: str, locale: str | None = None, default: str = "") -> str:
        row = self.tr(locale)
        return getattr(row, field, default) if row else default
