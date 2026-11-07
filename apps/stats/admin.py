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
from unfold.admin import ModelAdmin

from .models import MetricDay


@admin.register(MetricDay)
class MetricDayAdmin(ModelAdmin):
    list_display = ("submission", "metric", "galley", "date", "count")
    list_filter = ("metric", "date")
    search_fields = ("submission__id",)
    readonly_fields = ("submission", "galley", "metric", "date", "count")

    def has_add_permission(self, request):
        return False
