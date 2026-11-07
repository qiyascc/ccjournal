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

"""Yedek tatbikatı — `manage.py restore_drill [--file yedek.sqlite3]`.

"Yedeğimiz var" ile "yedeğimiz ÇALIŞIYOR" farklı şeylerdir. Bu komut en son
yedeği (backups/db-*.sqlite3) geçici bir kopyaya açar, bütünlük denetimi koşar
ve çekirdek tabloların sayımını raporlar — canlı veritabanına dokunmaz.
"""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

CORE_TABLES = ["journals_journal", "submissions_submission",
               "publications_publication", "accounts_user"]


class Command(BaseCommand):
    help = "Verify the latest (or given) SQLite backup restores cleanly."

    def add_arguments(self, parser):
        parser.add_argument("--file", default="",
                            help="Backup file (default: newest backups/db-*.sqlite3)")

    def handle(self, *args, **opts):
        base = Path(settings.BASE_DIR)
        if opts["file"]:
            src = Path(opts["file"])
        else:
            candidates = sorted((base / "backups").glob("db-*.sqlite3"))
            if not candidates:
                raise CommandError("No backups found under backups/ — create one "
                                   "first (see README 'Backups & preservation').")
            src = candidates[-1]
        if not src.exists():
            raise CommandError(f"Backup not found: {src}")

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "drill.sqlite3"
            shutil.copy2(src, work)
            con = sqlite3.connect(str(work))
            try:
                status = con.execute("PRAGMA integrity_check").fetchone()[0]
                if status != "ok":
                    raise CommandError(f"INTEGRITY FAILED for {src.name}: {status}")
                self.stdout.write(f"integrity_check: ok ({src.name}, "
                                  f"{src.stat().st_size // 1024} KB)")
                existing = {r[0] for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                for table in CORE_TABLES:
                    if table in existing:
                        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        self.stdout.write(f"  {table}: {n} row(s)")
                    else:
                        self.stdout.write(self.style.WARNING(
                            f"  {table}: MISSING (older schema?)"))
            finally:
                con.close()
        self.stdout.write(self.style.SUCCESS(
            "Restore drill passed — this backup opens and reads correctly."))
