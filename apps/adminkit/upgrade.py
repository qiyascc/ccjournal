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
Kayıtlı tüm Unfold admin'lerine import/export ekler (Unfold-stilli formlarla).
Özel change_list_template kullanan admin'ler atlanır (kurulum butonları korunur).
"""
from __future__ import annotations

from django.contrib import admin

SKIP = {"plugins.pluginstate", "themes.installedtheme"}


def upgrade_admins():
    try:
        from import_export.admin import ImportExportMixin
        from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
    except Exception:
        return

    site = admin.site
    for model, adminobj in list(site._registry.items()):
        label = f"{model._meta.app_label}.{model._meta.model_name}"
        if label in SKIP:
            continue
        cls = adminobj.__class__
        if issubclass(cls, ImportExportMixin):
            continue
        if getattr(cls, "change_list_template", None):
            continue
        new_cls = type(
            f"IE{cls.__name__}", (ImportExportMixin, cls),
            {"import_form_class": ImportForm,
             "export_form_class": SelectableFieldsExportForm,
             "__module__": cls.__module__},
        )
        try:
            site.unregister(model)
            site.register(model, new_cls)
        except Exception:
            site.register(model, cls)
