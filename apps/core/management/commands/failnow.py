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

"""ACİL GERİ YÜKLEME — `python manage.py failnow`

Proje yapısı bozulduğunda fabrika yapısını geri yükler ve Broadsheet temasını
aktive eder. Kaynak: config.ini `[repository] repo_url` (+ `github_token`,
`ref`) ayarlıysa GitHub'dan indirilen ve DOĞRULANAN tarball; değilse yerel
repository/snapshot.tar.gz (eski davranış). Yanlış/yabancı repo indirildiyse
hiçbir şey yazılmadan İngilizce "wrong repository" hatasıyla durur.

DOKUNULMAYANLAR (kullanıcı verisi):
  * config.ini                  (yapılandırma)
  * media/                      (yüklenen tüm dosyalar)
  * veritabanı (db.sqlite3*)    (içerik)
  * staticfiles/                (collectstatic çıktısı)
  * kullanıcı temaları          (themes/ altında snapshot'ta OLMAYAN klasörler)
  * static/ içindeki EKSTRA dosyalar (varsayılanlar geri yazılır, ekstralar silinmez)

TAM SIFIRLANANLAR (varsayılana döner; eklenen bozuk/yabancı dosyalar temizlenir):
  apps/, config/, templates/, locale/, plugins/, deploy/,
  manage.py, requirements.txt, deploy.sh, run.sh
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.repo_source import RepoSourceError, resolve_snapshot_root

REPLACE_DIRS = ["apps", "config", "templates", "locale", "plugins", "deploy"]
REPLACE_FILES = ["manage.py", "requirements.txt", "deploy.sh", "run.sh"]
MERGE_DIRS = ["static"]
THEMES_DIR = "themes"


class Command(BaseCommand):
    help = ("EMERGENCY: restore the default project structure (from the "
            "configured GitHub repository, or the local snapshot) and activate "
            "the Broadsheet theme. User themes, media, static extras and "
            "config.ini are left untouched.")

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true",
                            help="Skip the confirmation prompt.")
        parser.add_argument("--local", action="store_true",
                            help="Ignore [repository] repo_url and restore from "
                                 "the bundled local snapshot.")

    def _replace_tree(self, src: Path, dst: Path):
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    def _merge_tree(self, src: Path, dst: Path):
        for p in src.rglob("*"):
            rel = p.relative_to(src)
            target = dst / rel
            if p.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)

    def handle(self, *args, **opts):
        base = Path(settings.BASE_DIR)
        if not opts["yes"]:
            ans = input("This will RESET code/templates to the factory snapshot "
                        "(config.ini, media, DB, user themes, static extras are kept). "
                        "Type 'FAILNOW' to continue: ")
            if ans.strip() != "FAILNOW":
                self.stdout.write("Aborted.")
                return

        restored, kept = [], []
        with tempfile.TemporaryDirectory() as tmp:
            try:
                t, source_label = resolve_snapshot_root(
                    Path(tmp), base_dir=base, force_local=opts["local"])
            except RepoSourceError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"Restoring from: {source_label}")

            for d in REPLACE_DIRS:
                if (t / d).exists():
                    self._replace_tree(t / d, base / d)
                    restored.append(d + "/")
            for fl in REPLACE_FILES:
                if (t / fl).exists():
                    shutil.copy2(t / fl, base / fl)
                    restored.append(fl)

            for d in MERGE_DIRS:
                if (t / d).exists():
                    self._merge_tree(t / d, base / d)
                    restored.append(d + "/ (merged, extras kept)")

            tsrc = t / THEMES_DIR
            if tsrc.exists():
                builtins = [p.name for p in tsrc.iterdir() if p.is_dir()]
                for key in builtins:
                    self._replace_tree(tsrc / key, base / THEMES_DIR / key)
                restored.append(f"themes/ (built-ins: {', '.join(sorted(builtins))})")
                user_themes = [p.name for p in (base / THEMES_DIR).iterdir()
                               if p.is_dir() and p.name not in builtins]
                if user_themes:
                    kept.append(f"user themes: {', '.join(sorted(user_themes))}")

        kept += ["config.ini", "media/", "database", "staticfiles/", "static extras"]

        theme_msg = ""
        try:
            from apps.themes import loaders
            from apps.themes.services import discover, set_active
            discover()
            set_active("broadsheet")
            loaders.invalidate()
            theme_msg = "Active theme set to 'broadsheet'."
        except Exception as exc:  # noqa: BLE001
            theme_msg = f"Theme activation skipped (DB not reachable?): {exc}"

        self.stdout.write(self.style.SUCCESS("Factory structure restored."))
        for r in restored:
            self.stdout.write(f"  restored: {r}")
        for k in kept:
            self.stdout.write(f"  untouched: {k}")
        self.stdout.write(self.style.SUCCESS(theme_msg))
        self.stdout.write("Tip: restart the application server (systemd/gunicorn) "
                          "so restored code is reloaded.")
