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

from django.contrib import admin, messages
from unfold.admin import ModelAdmin

from .models import ConfigSetting
from .services import Config, _invalidate


@admin.register(ConfigSetting)
class ConfigSettingAdmin(ModelAdmin):
    list_display = ("section", "key", "display_value", "scope")
    list_filter = ("section",)
    search_fields = ("section", "key", "value")
    readonly_fields = ("section", "key")
    fields = ("section", "key", "value", "is_secret")

    @admin.display(description="Value")
    def display_value(self, obj):
        return obj.masked_value

    @admin.display(description="Scope")
    def scope(self, obj):
        return "boot (restart)" if obj.requires_restart else "live"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        Config.set(obj.section, obj.key, obj.value)
        _invalidate()
        if obj.requires_restart:
            self.message_user(
                request,
                f"'[{obj.section}] {obj.key}' saved to config.ini and DB. "
                "This is a boot setting — restart the server to apply.",
                level=messages.WARNING,
            )
        else:
            self.message_user(request, f"'[{obj.section}] {obj.key}' updated (file + DB).")
