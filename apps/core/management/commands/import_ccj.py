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

"""Kaskad paket içe aktarımı — `manage.py import_ccj paket.zip [--submitter email]`."""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Import a CC Journal submission package (built for a declined author)."

    def add_arguments(self, parser):
        parser.add_argument("zip_path")
        parser.add_argument("--submitter", default="",
                            help="Existing user email to own the submission.")

    def handle(self, *args, **opts):
        from apps.journals.models import Journal
        from apps.submissions.package import import_package

        path = Path(opts["zip_path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        journal = Journal.current()
        if not journal:
            raise CommandError("No journal configured — run /setup/ first.")
        submitter = None
        if opts["submitter"]:
            from apps.accounts.models import User
            submitter = User.objects.filter(email__iexact=opts["submitter"]).first()
            if not submitter:
                raise CommandError(f"No user with email {opts['submitter']}.")
        with path.open("rb") as fh:
            try:
                sub, info = import_package(fh, journal, submitter=submitter)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"Imported as submission #{sub.pk}: {info['translations']} translation(s), "
            f"{info['authors']} author(s), {info['files']} file(s). "
            f"Author workspace: /work/{sub.author_token}/"))
