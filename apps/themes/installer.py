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
Tema .zip kurucu — yalnızca veri (theme.json + theme.css). Kod çalıştırmaz.
zip-slip korumalı; tek kök klasör (= tema anahtarı) şartı.
"""
from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from .models import InstalledTheme
from .services import read_manifest, themes_dir

IGNORE = {"__MACOSX"}


class ThemeInstallError(Exception):
    pass


def install_theme_zip(fileobj) -> str:
    try:
        zf = zipfile.ZipFile(fileobj)
    except zipfile.BadZipFile:
        raise ThemeInstallError("Geçersiz .zip dosyası.")
    with zf:
        names = zf.namelist()
        for n in names:
            p = Path(n)
            if p.is_absolute() or ".." in p.parts:
                raise ThemeInstallError(f"Arşivde güvensiz yol: {n}")
        tops = {Path(n).parts[0] for n in names if n.strip("/") and Path(n).parts[0] not in IGNORE}
        if len(tops) != 1:
            raise ThemeInstallError("Arşiv tam olarak bir kök tema klasörü içermeli.")
        key = tops.pop()
        if not key.replace("-", "_").replace(".", "_").isidentifier():
            raise ThemeInstallError(f"Geçersiz tema adı: '{key}'")
        dest = themes_dir() / key
        with tempfile.TemporaryDirectory() as tmp:
            zf.extractall(tmp)
            src = Path(tmp) / key
            if not (src / "theme.json").exists():
                raise ThemeInstallError("Tema 'theme.json' içermeli.")
            if not (src / "theme.css").exists() and not (src / "templates").is_dir():
                raise ThemeInstallError("Tema 'theme.css' veya 'templates/' içermeli.")
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(src), str(dest))
    m = read_manifest(key)
    InstalledTheme.objects.update_or_create(
        key=m.get("key", key),
        defaults={"name": m.get("name", key), "version": m.get("version", "1.0.0"),
                  "author": m.get("author", ""), "description": m.get("description", "")},
    )
    return m.get("key", key)
