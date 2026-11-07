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

"""Menü admini — hedef (sistem/sayfa/URL) + dile göre opsiyonel etiketler."""
from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.locales import locale_label
from apps.journals.models import Journal

from .models import MenuItem, MenuItemLabel


def _locales():
    j = Journal.current()
    return list(j.supported_locales) if j else ["en"]


class BaseMenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ("area", "parent", "kind", "system_key", "page", "url", "seq", "is_enabled")


@admin.register(MenuItem)
class MenuItemAdmin(ModelAdmin):
    list_display = ("label_col", "area", "kind", "target_col", "seq", "is_enabled")
    list_editable = ("seq", "is_enabled")
    list_filter = ("area", "kind")
    ordering = ("area", "seq")

    def get_form(self, request, obj=None, **kwargs):
        locs = _locales()
        existing = {l.locale: l for l in obj.labels.all()} if obj and obj.pk else {}
        attrs = {"_locales": locs}
        for loc in locs:
            lab = existing.get(loc)
            attrs[f"label_{loc}"] = forms.CharField(
                label=f"Label · {locale_label(loc)}", required=False,
                initial=(lab.label if lab else ""),
                help_text="Boşsa sayfa başlığına / sistem varsayılanına düşer.")
        kwargs["form"] = type("MenuItemForm", (BaseMenuItemForm,), attrs)
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        locs = _locales()
        return [
            (None, {"fields": ("area", "parent", "seq", "is_enabled")}),
            ("Target", {"fields": ("kind", "system_key", "page", "url"),
                        "description": "kind=System ise system_key; Page ise page; URL ise url."}),
            ("Labels (optional)", {"fields": tuple(f"label_{loc}" for loc in locs)}),
        ]

    @admin.display(description="Item")
    def label_col(self, obj):
        return obj.default_label()

    @admin.display(description="Target")
    def target_col(self, obj):
        return obj.system_key or (obj.page.slug if obj.page_id else obj.url) or "—"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        supported = set(getattr(form, "_locales", []))
        for loc in supported:
            val = (form.cleaned_data.get(f"label_{loc}") or "").strip()
            if val:
                MenuItemLabel.objects.update_or_create(
                    item=obj, locale=loc, defaults={"label": val})
            else:
                MenuItemLabel.objects.filter(item=obj, locale=loc).delete()
        MenuItemLabel.objects.filter(item=obj).exclude(locale__in=supported).delete()
