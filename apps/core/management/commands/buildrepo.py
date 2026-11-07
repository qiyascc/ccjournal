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

"""Varsayılan yapının anlık görüntüsünü repository/snapshot.tar.gz olarak üretir.

Dahil: apps, config (config.ini HARİÇ), templates, locale, plugins, themes,
static, deploy, manage.py, requirements.txt, install.py, deploy.py, README.md
Hariç: config.ini, media, db.sqlite3*, staticfiles, repository, __pycache__, *.pyc
"""
from __future__ import annotations

import hashlib
import json
import tarfile
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

INCLUDE = ["apps", "config", "templates", "locale", "plugins", "themes",
           "static", "deploy", "manage.py", "requirements.txt",
           "install.py", "deploy.py", "README.md", "config.ini.example"]
EXCLUDE_NAMES = {"__pycache__", "db.sqlite3", "db.sqlite3-wal", "db.sqlite3-shm",
                 "node_modules", "auth", "run", "log"}


def _filter(ti: tarfile.TarInfo):
    p = Path(ti.name)
    if any(part in EXCLUDE_NAMES for part in p.parts):
        return None
    if p.name.endswith(".pyc"):
        return None
    if p.name == "config.ini":
        return None
    return ti


class Command(BaseCommand):
    help = "Rebuild repository/snapshot.tar.gz from the current project structure."

    def handle(self, *args, **opts):
        base = Path(settings.BASE_DIR)
        repo = base / "repository"
        repo.mkdir(exist_ok=True)
        out = repo / "snapshot.tar.gz"
        n = 0
        with tarfile.open(out, "w:gz") as tar:
            for item in INCLUDE:
                p = base / item
                if not p.exists():
                    continue
                tar.add(p, arcname=item, filter=_filter)
                n += 1
        sha = hashlib.sha256(out.read_bytes()).hexdigest()
        manifest = {"created": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "items": INCLUDE, "sha256": sha,
                    "size": out.stat().st_size}
        (repo / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
        (repo / "README.md").write_text(
            "# repository/\n\nPristine snapshot of the default project structure.\n\n"
            "* Restore automatically: `python manage.py failnow --yes`\n"
            "* Restore manually (if manage.py itself is broken):\n"
            "  `tar -xzf repository/snapshot.tar.gz -C .`\n\n"
            "Never includes: `config.ini`, `media/`, database files, `staticfiles/`.\n")
        self.stdout.write(self.style.SUCCESS(
            f"Snapshot written: {out} ({manifest['size']//1024} KB, {n} top-level items)"))
