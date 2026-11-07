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

"""Duyuru admini — derginin desteklediği her dile göre otomatik alanlar (pages deseni)."""
from django import forms
from django.contrib import admin
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin
from rangefilter.filters import DateRangeFilterBuilder

from apps.core.locales import locale_label
from apps.journals.models import Journal

from .models import Announcement, AnnouncementTranslation


def _supported():
    j = Journal.current()
    return (list(j.supported_locales) if j else ["en"], j.primary_locale if j else "en")


class BaseAnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ("date_posted", "date_expire", "is_published")


@admin.register(Announcement)
class AnnouncementAdmin(ModelAdmin):
    list_display = ("__str__", "languages", "date_posted", "date_expire", "is_published")
    list_filter = ("is_published", ("date_posted", DateRangeFilterBuilder(title="Posted")))
    list_editable = ("is_published",)
    date_hierarchy = "date_posted"
    search_fields = ("translations__title", "translations__short_description")

    def get_form(self, request, obj=None, **kwargs):
        locales, primary = _supported()
        existing = {t.locale: t for t in obj.translations.all()} if obj and obj.pk else {}
        attrs = {"_locales": locales}
        for loc in locales:
            label = locale_label(loc)
            t = existing.get(loc)
            attrs[f"title_{loc}"] = forms.CharField(
                label=f"Title · {label}", required=(loc == primary),
                initial=(t.title if t else ""))
            attrs[f"short_{loc}"] = forms.CharField(
                label=f"Short description · {label}", required=False,
                widget=forms.Textarea(attrs={"rows": 2}),
                initial=(t.short_description if t else ""))
            attrs[f"body_{loc}"] = forms.CharField(
                label=f"Body · {label}", required=False,
                widget=CKEditor5Widget(config_name="default"),
                initial=(t.body if t else ""))
        kwargs["form"] = type("AnnouncementForm", (BaseAnnouncementForm,), attrs)
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        locales, _ = _supported()
        base = [(None, {"fields": ("date_posted", "date_expire", "is_published")})]
        return base + [(locale_label(loc),
                        {"fields": (f"title_{loc}", f"short_{loc}", f"body_{loc}")})
                       for loc in locales]

    @admin.display(description="Languages")
    def languages(self, obj):
        return ", ".join(t.locale for t in obj.translations.all()) or "—"

    def save_model(self, request, obj, form, change):
        if obj.journal_id is None:
            obj.journal = Journal.current()
        super().save_model(request, obj, form, change)
        supported = set(getattr(form, "_locales", []))
        for loc in supported:
            title = (form.cleaned_data.get(f"title_{loc}") or "").strip()
            short = form.cleaned_data.get(f"short_{loc}") or ""
            body = form.cleaned_data.get(f"body_{loc}") or ""
            if title or short or body:
                AnnouncementTranslation.objects.update_or_create(
                    announcement=obj, locale=loc,
                    defaults={"title": title or "(untitled)",
                              "short_description": short, "body": body})
            else:
                AnnouncementTranslation.objects.filter(announcement=obj, locale=loc).delete()
        AnnouncementTranslation.objects.filter(announcement=obj).exclude(
            locale__in=supported).delete()
