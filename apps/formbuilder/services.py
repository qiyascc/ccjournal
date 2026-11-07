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
FormService — dinamik form üretimi, başvuru kaydı, durum akışı + e-posta, reject arşivi.
"""
from __future__ import annotations

import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from .models import (FieldType, Form, FormSubmission, SubmissionStatus,
                     SubmissionUpload)

_PHONE_RE = re.compile(r"^[0-9+()\-\s]{6,20}$")


def normalize_orcid(raw: str) -> str:
    """'0000-0002-1825-0097' VE '0000000218250097' formatlarını kabul eder,
    checksum (ISO 7064 11-2) doğrular, tireli kanonik forma çevirir."""
    s = re.sub(r"[\s\-]", "", (raw or "")).upper()
    s = s.removeprefix("HTTPS://ORCID.ORG/").removeprefix("HTTP://ORCID.ORG/")
    if not re.fullmatch(r"\d{15}[\dX]", s):
        raise ValidationError("ORCID must be 16 digits (xxxx-xxxx-xxxx-xxxx).")
    total = 0
    for ch in s[:-1]:
        total = (total + int(ch)) * 2
    check = (12 - (total % 11)) % 11
    expected = "X" if check == 10 else str(check)
    if s[-1] != expected:
        raise ValidationError("Invalid ORCID (checksum mismatch).")
    return f"{s[0:4]}-{s[4:8]}-{s[8:12]}-{s[12:16]}"


def _orcid_clean(value):
    return normalize_orcid(value) if value else value


def _phone_clean(value):
    if value and not _PHONE_RE.match(value.strip()):
        raise ValidationError("Enter a valid phone number.")
    return (value or "").strip()


def _locale_choices(journal):
    from apps.core.locales import locale_label
    locs = (journal.supported_locales if journal else None) or ["en"]
    return [(c, locale_label(c)) for c in locs]


def build_django_form(form: Form, journal=None):
    """FormField tanımlarından gerçek bir django.forms.Form sınıfı üretir."""
    attrs: dict = {}
    for f in form.fields.filter(is_active=True):
        kw = dict(label=f.label, required=f.required, help_text=f.help_text)
        widget_attrs = {"class": "field"}
        if f.placeholder:
            widget_attrs["placeholder"] = f.placeholder
        t = f.field_type
        if t == FieldType.TEXT:
            fld = forms.CharField(max_length=f.max_length or 255,
                                  widget=forms.TextInput(attrs=widget_attrs), **kw)
        elif t == FieldType.TEXTAREA:
            fld = forms.CharField(widget=forms.Textarea(
                attrs={**widget_attrs, "rows": 5}), **kw)
        elif t == FieldType.EMAIL:
            fld = forms.EmailField(widget=forms.EmailInput(attrs=widget_attrs), **kw)
        elif t == FieldType.PHONE:
            fld = forms.CharField(widget=forms.TextInput(
                attrs={**widget_attrs, "inputmode": "tel"}), **kw)
        elif t == FieldType.ORCID:
            fld = forms.CharField(widget=forms.TextInput(attrs={
                **widget_attrs, "placeholder": f.placeholder or "0000-0000-0000-0000"}), **kw)
        elif t == FieldType.SELECT:
            fld = forms.ChoiceField(choices=[(c, c) for c in (f.choices or [])],
                                    widget=forms.Select(attrs=widget_attrs), **kw)
        elif t == FieldType.LOCALE:
            fld = forms.ChoiceField(choices=_locale_choices(journal),
                                    widget=forms.Select(attrs=widget_attrs), **kw)
        elif t == FieldType.KEYWORDS:
            fld = forms.CharField(widget=forms.TextInput(attrs={
                **widget_attrs, "placeholder": f.placeholder or "keyword1, keyword2, …"}), **kw)
        elif t == FieldType.FILE:
            fld = forms.FileField(widget=forms.ClearableFileInput(
                attrs={"class": "field"}), **kw)
        elif t == FieldType.CHECKBOX:
            fld = forms.BooleanField(**kw)
        elif t == FieldType.NUMBER:
            fld = forms.DecimalField(widget=forms.NumberInput(attrs=widget_attrs), **kw)
        elif t == FieldType.DATE:
            fld = forms.DateField(widget=forms.DateInput(
                attrs={**widget_attrs, "type": "date"}), **kw)
        else:
            continue
        attrs[f.slug] = fld
        if t == FieldType.ORCID:
            attrs[f"clean_{f.slug}"] = (
                lambda self, _slug=f.slug: _orcid_clean(self.cleaned_data.get(_slug)))
        if t == FieldType.PHONE:
            attrs[f"clean_{f.slug}"] = (
                lambda self, _slug=f.slug: _phone_clean(self.cleaned_data.get(_slug)))
    return type(f"DynamicForm_{form.slug}", (forms.Form,), attrs)


class FormService:
    @staticmethod
    def save_entry(form: Form, cleaned: dict, files: dict, *, locale="") -> FormSubmission:
        data, name_parts, email = {}, [], ""
        file_fields = {f.slug for f in form.fields.filter(field_type=FieldType.FILE)}
        for f in form.fields.filter(is_active=True):
            if f.slug in file_fields:
                continue
            val = cleaned.get(f.slug)
            data[f.slug] = str(val) if val is not None else ""
            if f.field_type == FieldType.EMAIL and val and not email:
                email = str(val)
            if f.field_type == FieldType.TEXT and f.slug in ("first_name", "last_name",
                                                             "name", "ad", "soyad"):
                name_parts.append(str(val))
        entry = FormSubmission.objects.create(
            form=form, data=data, submitter_email=email,
            submitter_name=" ".join(p for p in name_parts if p), locale=locale)
        for slug in file_fields:
            up = files.get(slug)
            if up:
                SubmissionUpload.objects.create(
                    submission=entry, field_slug=slug, file=up,
                    original_name=getattr(up, "name", "file"))
        if form.notify_submitter and email:
            FormService._mail(entry, "form_received",
                              "We received your submission",
                              "Dear {name},\n\nThank you — we received your submission "
                              "\"{form}\". Our team will review it and get back to you "
                              "shortly.\n\nRegards,\n{journal}")
        return entry

    @staticmethod
    def set_status(entry: FormSubmission, status: int, user=None) -> FormSubmission:
        if entry.status == status:
            return entry
        entry.status = status
        entry.decided_by = user
        entry.decided_at = timezone.now()
        entry.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
        if status == SubmissionStatus.REJECTED:
            FormService._archive_uploads(entry)
            FormService._mail(entry, "form_rejected", "Your submission was not accepted",
                              "Dear {name},\n\nThank you for your interest. After review, "
                              "we are unable to accept your submission \"{form}\" at this "
                              "time.\n\nRegards,\n{journal}")
        elif status == SubmissionStatus.APPROVED:
            FormService._mail(entry, "form_approved", "Your submission moved forward",
                              "Dear {name},\n\nGood news — your submission \"{form}\" has "
                              "been approved and moved to the next stage. We will contact "
                              "you with the next steps.\n\nRegards,\n{journal}")
        return entry

    @staticmethod
    def _archive_uploads(entry: FormSubmission):
        """Reddedilen başvurunun dosyalarını SİLMEDEN media/reject/ altına taşır."""
        for u in entry.uploads.all():
            old = u.file.name
            if old.startswith("reject/") or not default_storage.exists(old):
                continue
            new = f"reject/{old}"
            with default_storage.open(old, "rb") as fh:
                saved = default_storage.save(new, ContentFile(fh.read()))
            default_storage.delete(old)
            u.file.name = saved
            u.save(update_fields=["file"])

    @staticmethod
    def _mail(entry: FormSubmission, key: str, fb_subject: str, fb_body: str):
        if not entry.submitter_email:
            return
        from apps.comms.services import MailService
        from apps.journals.models import Journal
        journal = entry.form.journal or Journal.current()
        locale = entry.locale or (journal.primary_locale if journal else "en")
        ctx = {"name": entry.submitter_name or "author", "form": entry.form.title,
               "journal": str(journal) if journal else "", "data": entry.data}
        sent = MailService.send(key, journal=journal, locale=locale,
                                to=[entry.submitter_email], context=ctx, related=entry)
        if not sent:
            from django.conf import settings as dj
            from django.core.mail import send_mail
            subject = fb_subject
            body = fb_body.format(name=ctx["name"], form=ctx["form"], journal=ctx["journal"])
            html = MailService._html(subject, body, journal)
            try:
                send_mail(subject, body,
                          getattr(dj, "DEFAULT_FROM_EMAIL", "noreply@example.org"),
                          [entry.submitter_email], fail_silently=True, html_message=html)
            except Exception:
                pass
