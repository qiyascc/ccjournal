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

"""Yıllık hakem teşekkür özeti — `manage.py reviewer_year_summary [--year N] [--send]`.

--send verilmezse yalnız listeler (kuru koşu). Ocak başında elle ya da cron ile
çalıştırılır; her hakeme o yılki katkısının özetini e-postalar.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Email each reviewer a summary of their completed reviews for a year."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=timezone.now().year - 1)
        parser.add_argument("--send", action="store_true",
                            help="Actually send emails (default: dry-run list).")

    def handle(self, *args, **opts):
        from apps.accounts.models import User

        from apps.review.certificates import send_year_summary, year_stats

        year = opts["year"]
        users = (User.objects.filter(
            review_assignments__date_completed__year=year).distinct())
        listed = sent = 0
        for u in users:
            stats = year_stats(u, year)
            if not stats:
                continue
            listed += 1
            line = (f"{u.full_name or u.email}: {stats['completed']} review(s), "
                    f"avg {stats['avg_days']} days, {stats['on_time']} on time")
            if opts["send"]:
                ok = send_year_summary(u, year)
                sent += int(ok)
                line += "  → sent" if ok else "  → SKIPPED (no email/channel)"
            self.stdout.write(line)
        tail = f"Sent {sent} email(s)." if opts["send"] else "Dry-run (use --send)."
        self.stdout.write(self.style.SUCCESS(
            f"{listed} reviewer(s) with completed reviews in {year}. {tail}"))
