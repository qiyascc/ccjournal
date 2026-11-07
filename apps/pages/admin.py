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
Statik sayfa admini — Unfold *yerleşik sekmeleri* + CKEditor 5 + SEO/meta.

Karar notu: django-content-editor blok-tabanlı ve Unfold-native olmadığı için
KULLANILMADI; bunun yerine zaten projede olan CKEditor 5, Unfold'un change-form
sekme mekanizmasıyla (fieldset classes=["tab"]) birleştirildi.

Sekmeler:
  - "Content · <Dil>"  → dil başına: title, CKEditor içerik, meta_title, meta_description
  - "SEO & meta"       → global: canonical_url, robots_noindex, og_image
  - "Settings"         → slug, is_published, show_in_menu, seq
"""
from django import forms
from django.contrib import admin
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin

from apps.core.locales import locale_label
from apps.journals.models import Journal

from .models import StaticPage, StaticPageTranslation


def _supported():
    j = Journal.current()
    return (list(j.supported_locales) if j else ["en"], j.primary_locale if j else "en")


class BaseStaticPageForm(forms.ModelForm):
    class Meta:
        model = StaticPage
        fields = ("slug", "is_published", "show_in_menu", "seq",
                  "canonical_url", "robots_noindex", "og_image")


@admin.register(StaticPage)
class StaticPageAdmin(ModelAdmin):
    list_display = ("slug", "languages", "is_published", "show_in_menu",
                    "robots_noindex", "seq")
    list_editable = ("is_published", "show_in_menu", "seq")
    list_filter = ("is_published", "show_in_menu", "robots_noindex")
    search_fields = ("slug", "translations__title")

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
            attrs[f"content_{loc}"] = forms.CharField(
                label=f"Content · {label}", required=False,
                widget=CKEditor5Widget(config_name="default"),
                initial=(t.content if t else ""))
            attrs[f"meta_title_{loc}"] = forms.CharField(
                label=f"Meta title · {label}", required=False, max_length=70,
                help_text="Boşsa sayfa başlığı kullanılır (max 70)",
                initial=(t.meta_title if t else ""))
            attrs[f"meta_description_{loc}"] = forms.CharField(
                label=f"Meta description · {label}", required=False, max_length=160,
                widget=forms.Textarea(attrs={"rows": 2}),
                help_text="Arama sonucu açıklaması (max 160)",
                initial=(t.meta_description if t else ""))
        kwargs["form"] = type("StaticPageForm", (BaseStaticPageForm,), attrs)
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        """Unfold sekmeleri: fieldset'e classes=["tab"] + isim → sekme."""
        locales, _primary = _supported()
        fieldsets = []
        for loc in locales:
            fieldsets.append((f"Content · {locale_label(loc)}", {
                "classes": ["tab"],
                "fields": (f"title_{loc}", f"content_{loc}",
                           f"meta_title_{loc}", f"meta_description_{loc}"),
            }))
        fieldsets.append(("SEO & meta", {
            "classes": ["tab"],
            "fields": ("canonical_url", "robots_noindex", "og_image"),
        }))
        fieldsets.append(("Settings", {
            "classes": ["tab"],
            "fields": ("slug", "is_published", "show_in_menu", "seq"),
        }))
        return fieldsets

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
            content = form.cleaned_data.get(f"content_{loc}") or ""
            meta_title = (form.cleaned_data.get(f"meta_title_{loc}") or "").strip()
            meta_desc = (form.cleaned_data.get(f"meta_description_{loc}") or "").strip()
            if title or content:
                StaticPageTranslation.objects.update_or_create(
                    page=obj, locale=loc,
                    defaults={"title": title or obj.slug, "content": content,
                              "meta_title": meta_title,
                              "meta_description": meta_desc})
            else:
                StaticPageTranslation.objects.filter(page=obj, locale=loc).delete()
        StaticPageTranslation.objects.filter(page=obj).exclude(locale__in=supported).delete()
