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
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import path
from unfold.admin import ModelAdmin

from .installer import InstallError, install_zip
from .models import PluginSetting, PluginState
from .registry import registry


@admin.register(PluginState)
class PluginStateAdmin(ModelAdmin):
    change_list_template = "admin/plugins/pluginstate_changelist.html"
    list_display = ("plugin_key", "plugin_name", "category", "version", "enabled", "manage_link")

    @admin.display(description="Manage")
    def manage_link(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse
        if obj.plugin_key == "whatsapp":
            return format_html('<a class="button" href="{}">QR / status</a>',
                               reverse("admin:plugins_whatsapp_manage"))
        if obj.plugin_key == "telegram":
            return format_html('<a class="button" href="{}">Token / status</a>',
                               reverse("admin:plugins_telegram_manage"))
        return "—"
    list_editable = ("enabled",)
    readonly_fields = ("plugin_key",)

    def get_urls(self):
        custom = [
            path("install/", self.admin_site.admin_view(self.install_view),
                 name="plugins_pluginstate_install"),
            path("whatsapp/", self.admin_site.admin_view(self.whatsapp_view),
                 name="plugins_whatsapp_manage"),
            path("whatsapp/status/", self.admin_site.admin_view(self.whatsapp_status),
                 name="plugins_whatsapp_status"),
            path("whatsapp/<str:op>/", self.admin_site.admin_view(self.whatsapp_action),
                 name="plugins_whatsapp_action"),
            path("telegram/", self.admin_site.admin_view(self.telegram_view),
                 name="plugins_telegram_manage"),
            path("telegram/<str:op>/", self.admin_site.admin_view(self.telegram_action),
                 name="plugins_telegram_action"),
        ]
        return custom + super().get_urls()

    def telegram_view(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied
        from plugins.telegram import client
        enabled = registry.is_enabled("telegram")
        if request.method == "POST" and enabled:
            tok = request.POST.get("token", "").strip()
            client.set_setting("token", tok)
            client.restart()
            messages.success(request, "Telegram token saved; bot restarted.")
            return redirect("admin:plugins_telegram_manage")
        ctx = {**self.admin_site.each_context(request),
               "title": "Telegram", "opts": self.model._meta, "enabled": enabled,
               "running": client.is_running() if enabled else False,
               "token": client.token() if enabled else "",
               "bot_username": (client.bot_username() if enabled and client.token() else "")}
        return render(request, "admin/plugins/telegram.html", ctx)

    def telegram_action(self, request, op):
        if not request.user.is_superuser:
            raise PermissionDenied
        from plugins.telegram import client
        if op == "restart":
            client.restart()
            messages.success(request, "Telegram bot restarted.")
        return redirect("admin:plugins_telegram_manage")

    def whatsapp_view(self, request):
        """WhatsApp plugin yönetim sayfası: QR + bağlantı durumu."""
        if not request.user.is_superuser:
            raise PermissionDenied
        from plugins.whatsapp import client
        enabled = registry.is_enabled("whatsapp")
        ctx = {**self.admin_site.each_context(request),
               "title": "WhatsApp", "opts": self.model._meta,
               "enabled": enabled, "running": client.is_running()}
        return render(request, "admin/plugins/whatsapp.html", ctx)

    def whatsapp_status(self, request):
        """Canlı durum (JS polling için JSON)."""
        from django.http import JsonResponse
        if not request.user.is_superuser:
            raise PermissionDenied
        from plugins.whatsapp import client
        return JsonResponse(client.status())

    def whatsapp_action(self, request, op):
        from django.http import JsonResponse
        if not request.user.is_superuser:
            raise PermissionDenied
        from plugins.whatsapp import client
        if op == "logout":
            client.logout()
        elif op == "restart":
            client.stop(); client.start()
        elif op == "start":
            client.start()
        return JsonResponse({"ok": True})

    def _orig_get_urls(self):
        return super().get_urls()

    def install_view(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied
        if request.method == "POST" and request.FILES.get("package"):
            try:
                key = install_zip(request.FILES["package"])
                self.message_user(
                    request, f"Plugin '{key}' installed. Enable it from the list below.")
                return redirect("..")
            except InstallError as e:
                self.message_user(request, str(e), level=messages.ERROR)
        ctx = {**self.admin_site.each_context(request), "title": "Install plugin (.zip)",
               "opts": self.model._meta}
        return render(request, "admin/plugins/install.html", ctx)

    def get_queryset(self, request):
        for p in registry.all():
            PluginState.objects.get_or_create(plugin_key=p.key, defaults={"enabled": False})
        return super().get_queryset(request)

    def _plugin(self, obj):
        return registry.get(obj.plugin_key)

    @admin.display(description="Name")
    def plugin_name(self, obj):
        p = self._plugin(obj)
        return p.name if p else "—"

    @admin.display(description="Category")
    def category(self, obj):
        p = self._plugin(obj)
        return p.category if p else "—"

    @admin.display(description="Version")
    def version(self, obj):
        p = self._plugin(obj)
        return p.version if p else "—"

    def has_add_permission(self, request):
        return False


@admin.register(PluginSetting)
class PluginSettingAdmin(ModelAdmin):
    list_display = ("plugin_key", "journal", "key", "value")
    list_filter = ("plugin_key",)
