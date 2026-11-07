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
Aktif temanın templates/ klasörünü ilk sırada tarayan loader.

Tam tema desteği: aktif tema `themes/<key>/templates/...` altında herhangi bir şablonu
(base.html, web/home.html, web/article.html, ...) ezebilir. Tema şablon sağlamıyorsa
varsayılan şablonlara düşülür. Aktif anahtar önbelleğe alınır (tema değişince temizlenir).
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.template.loaders.filesystem import Loader as FilesystemLoader

_ACTIVE_DIR: list | None = None


def invalidate():
    global _ACTIVE_DIR
    _ACTIVE_DIR = None


def _active_dirs():
    global _ACTIVE_DIR
    if _ACTIVE_DIR is None:
        dirs = []
        try:
            from .services import active_theme
            t = active_theme()
            if t:
                p = Path(settings.BASE_DIR) / "themes" / t.key / "templates"
                if p.is_dir():
                    dirs = [str(p)]
        except Exception:
            dirs = []
        _ACTIVE_DIR = dirs
    return _ACTIVE_DIR


class ThemeTemplateLoader(FilesystemLoader):
    def get_dirs(self):
        return _active_dirs()
