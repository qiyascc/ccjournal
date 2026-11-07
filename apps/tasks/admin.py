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

from django.contrib import admin
from django.utils import timezone
from unfold.admin import ModelAdmin

from .models import Job


@admin.register(Job)
class JobAdmin(ModelAdmin):
    list_display = ("id", "func", "queue", "status", "attempts", "run_after", "finished_at")
    list_filter = ("status", "queue")
    search_fields = ("func", "last_error")
    readonly_fields = ("func", "args", "kwargs", "attempts", "started_at", "finished_at",
                       "result", "last_error", "created_at")
    actions = ["requeue"]

    @admin.action(description="Requeue selected jobs (run now)")
    def requeue(self, request, queryset):
        n = queryset.update(status=Job.Status.QUEUED, run_after=timezone.now(),
                            started_at=None)
        self.message_user(request, f"{n} job(s) requeued.")
