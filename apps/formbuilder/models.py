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
Form Engine (Faz 18.3) — tam form-builder.

* Form: kart olarak listelenen, slug'la erişilen özel form (alanları düzenlenebilir).
* FormField: sürükle-bırak benzeri `seq` sıralı, tipli alanlar (text/textarea/email/
  phone/orcid/select/locale_select/keywords/file/checkbox/number/date).
* FormSubmission: gelen veri JSON olarak; durum akışı NEW → APPROVED / REJECTED.
  Reddedilen başvuruların dosyaları SİLİNMEZ — media/reject/ altına taşınır.
* SubmissionUpload: başvuruya bağlı dosyalar (alan bazında).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class FieldType(models.TextChoices):
    TEXT = "text", "Short text"
    TEXTAREA = "textarea", "Paragraph"
    EMAIL = "email", "Email"
    PHONE = "phone", "Phone"
    ORCID = "orcid", "ORCID iD"
    SELECT = "select", "Dropdown (custom choices)"
    LOCALE = "locale_select", "Dropdown (journal languages)"
    KEYWORDS = "keywords", "Keywords (comma separated)"
    FILE = "file", "File upload"
    CHECKBOX = "checkbox", "Checkbox"
    NUMBER = "number", "Number"
    DATE = "date", "Date"


class Form(TimeStampedModel):
    journal = models.ForeignKey("journals.Journal", on_delete=models.CASCADE,
                                related_name="custom_forms", null=True, blank=True)
    slug = models.SlugField(max_length=64, unique=True,
                            help_text="URL: form.<domain>/<slug>/")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, help_text="Kartta ve form başında görünür")
    is_active = models.BooleanField(default=True)
    seq = models.PositiveIntegerField(default=0)
    success_message = models.TextField(
        blank=True, default="Thank you! Your submission has been received. "
                            "We will get back to you shortly.")
    notify_submitter = models.BooleanField(
        default=True, help_text="Gönderene otomatik onay e-postası gönder")
    is_protected = models.BooleanField(
        default=False, help_text="Sistem formu (ör. varsayılan submission) — silinemez")

    class Meta:
        ordering = ["seq", "slug"]
        verbose_name = "Form"

    def __str__(self) -> str:
        return self.title


class FormField(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="fields")
    label = models.CharField(max_length=200)
    slug = models.SlugField(max_length=64, help_text="Veri anahtarı (form içinde benzersiz)")
    field_type = models.CharField(max_length=20, choices=FieldType.choices,
                                  default=FieldType.TEXT)
    required = models.BooleanField(default=False)
    help_text = models.CharField(max_length=255, blank=True)
    placeholder = models.CharField(max_length=120, blank=True)
    choices = models.JSONField(default=list, blank=True,
                               help_text='SELECT için: ["A", "B", ...]')
    max_length = models.PositiveIntegerField(null=True, blank=True)
    seq = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["seq", "id"]
        unique_together = ("form", "slug")

    def __str__(self) -> str:
        return f"{self.form.slug}.{self.slug} ({self.field_type})"


class SubmissionStatus(models.IntegerChoices):
    NEW = 1, "New"
    APPROVED = 2, "Approved (advanced)"
    REJECTED = 3, "Rejected"


class FormSubmission(TimeStampedModel):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="entries")
    status = models.IntegerField(choices=SubmissionStatus.choices,
                                 default=SubmissionStatus.NEW)
    data = models.JSONField(default=dict)
    submitter_email = models.EmailField(blank=True)
    submitter_name = models.CharField(max_length=200, blank=True)
    locale = models.CharField(max_length=12, blank=True)
    note = models.TextField(blank=True, help_text="Dahili not (gönderene gitmez)")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Form submission"
        permissions = [("decide_formsubmission", "Can approve/reject form submissions")]

    def __str__(self) -> str:
        who = self.submitter_name or self.submitter_email or f"#{self.pk}"
        return f"{self.form.slug} · {who}"


def upload_to(instance, filename):
    return f"formbuilder/{instance.submission.form.slug}/{instance.submission_id or 'tmp'}/{filename}"


class SubmissionUpload(models.Model):
    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE,
                                   related_name="uploads")
    field_slug = models.SlugField(max_length=64)
    file = models.FileField(upload_to=upload_to, max_length=400)
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.original_name
