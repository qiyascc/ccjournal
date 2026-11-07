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

"""Plugin şablon yükleyicisi — plugin'leri tamamen self-contained yapar.

Her plugin kendi `templates/` klasörünü taşıyabilir (ör. admin sayfaları). Bu
yükleyici `plugins/*/templates/` dizinlerini Django şablon arama yoluna ekler.
Böylece bir plugin'in admin template'i ayrı bir yere kopyalanmadan, plugin
klasörünün içinden servis edilir — tek zip, sunucuya elle dosya koymak yok.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.template.loaders.filesystem import Loader as FilesystemLoader


def _plugin_template_dirs() -> list[str]:
    base = Path(settings.BASE_DIR) / "plugins"
    if not base.exists():
        return []
    dirs = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        tdir = child / "templates"
        if tdir.is_dir():
            dirs.append(str(tdir))
    return dirs


class PluginTemplateLoader(FilesystemLoader):
    """plugins/*/templates/ klasörlerinden şablon yükler."""

    def get_dirs(self):
        return _plugin_template_dirs()
