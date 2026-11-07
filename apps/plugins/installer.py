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
Plugin .zip kurucu.

Admin panelinden yüklenen .zip'i plugins/ altına açar, import edip kaydeder.
Güvenlik: yalnızca superuser çağırmalı (admin view'da zorlanır); zip-slip koruması;
tek kök paket klasörü şartı; __init__.py + `plugin` örneği doğrulaması.

Not: plugin'ler kod çalıştırır (OJS'te de öyle). Bu yüzden kurulum güvenilir bir
yönetici işlemidir; arayüzde superuser ile sınırlandırılmıştır.
"""
from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings

from .models import PluginState
from .registry import registry

IGNORE_TOPS = {"__MACOSX"}


class InstallError(Exception):
    pass


def _plugins_dir() -> Path:
    d = Path(settings.BASE_DIR) / "plugins"
    d.mkdir(exist_ok=True)
    return d


def _top_level_package(names: list[str]) -> str:
    tops = set()
    for n in names:
        n = n.strip("/")
        if not n:
            continue
        top = n.split("/")[0]
        if top not in IGNORE_TOPS:
            tops.add(top)
    if len(tops) != 1:
        raise InstallError(
            "Arşiv tam olarak bir kök plugin klasörü içermeli "
            f"(bulunan: {sorted(tops) or 'yok'})."
        )
    pkg = tops.pop()
    if not pkg.isidentifier() or pkg.startswith("_"):
        raise InstallError(f"Geçersiz paket adı: '{pkg}'")
    return pkg


def install_zip(fileobj) -> str:
    """Plugin .zip'ini kurar ve plugin anahtarını döndürür."""
    try:
        zf = zipfile.ZipFile(fileobj)
    except zipfile.BadZipFile:
        raise InstallError("Geçersiz .zip dosyası.")

    with zf:
        names = zf.namelist()
        for n in names:
            p = Path(n)
            if p.is_absolute() or ".." in p.parts:
                raise InstallError(f"Arşivde güvensiz yol: {n}")
        pkg = _top_level_package(names)
        dest = _plugins_dir() / pkg
        with tempfile.TemporaryDirectory() as tmp:
            zf.extractall(tmp)
            src = Path(tmp) / pkg
            if not (src / "__init__.py").exists():
                raise InstallError(f"Plugin '{pkg}/__init__.py' içermeli.")
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(src), str(dest))

    importlib.invalidate_caches()
    modname = f"plugins.{pkg}"
    try:
        if modname in sys.modules:
            module = importlib.reload(sys.modules[modname])
        else:
            module = importlib.import_module(modname)
    except Exception as e:
        shutil.rmtree(dest, ignore_errors=True)
        raise InstallError(f"Plugin import edilemedi: {e}")

    plugin = getattr(module, "plugin", None)
    if plugin is None or not getattr(plugin, "key", ""):
        shutil.rmtree(dest, ignore_errors=True)
        raise InstallError("Paket bir `plugin` örneği (key ile) açığa çıkarmalı.")

    try:
        _run_install_steps(dest)
    except InstallError:
        raise
    except Exception as e:
        import logging
        logging.getLogger("plugins").warning("install steps for %s failed: %s", pkg, e)

    registry.register_plugin(plugin)
    PluginState.objects.get_or_create(plugin_key=plugin.key, defaults={"enabled": False})
    return plugin.key


def _run_install_steps(plugin_dir: Path) -> None:
    """plugin.json'daki kurulum adımlarını çalıştırır (şimdilik: npm install).

    Böylece sidecar bağımlılıkları sunucuya elle girmeden, zip kurulumunda
    otomatik kurulur. Node yoksa açıklayıcı hata verir.
    """
    manifest = plugin_dir / "plugin.json"
    if not manifest.exists():
        return
    import json
    import shutil as _sh
    import subprocess
    try:
        data = json.loads(manifest.read_text())
    except (ValueError, OSError):
        return
    steps_npm = (data.get("install") or {}).get("npm") or []
    steps_pip = (data.get("install") or {}).get("pip") or []
    if steps_npm:
        npm = _sh.which("npm")
        if not npm:
            raise InstallError(
                "Bu plugin bir Node.js sidecar içeriyor ancak 'npm' bulunamadı. "
                "Sunucuya Node.js kurun (ör. install.py ile) ve plugin'i yeniden yükleyin.")
        for step in steps_npm:
            sub = plugin_dir / step.get("dir", "")
            if not (sub / "package.json").exists():
                continue
            subprocess.run([npm, "install", "--no-audit", "--no-fund"],
                           cwd=str(sub), check=True, capture_output=True, timeout=600)
    if steps_pip:
        import sys as _sys
        for step in steps_pip:
            req = plugin_dir / step.get("requirements", "")
            if not req.exists():
                continue
            subprocess.run([_sys.executable, "-m", "pip", "install", "-r", str(req)],
                           check=True, capture_output=True, timeout=600)
