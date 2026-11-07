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

from .installer import ThemeInstallError, install_theme_zip
from .models import InstalledTheme


@admin.register(InstalledTheme)
class InstalledThemeAdmin(ModelAdmin):
    change_list_template = "admin/themes/installedtheme_changelist.html"
    list_display = ("name", "key", "version", "author", "is_active")
    actions = ["make_active"]
    readonly_fields = ("key", "version", "author", "description")

    @admin.action(description="Set selected theme as active")
    def make_active(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one theme.", level=messages.ERROR)
            return
        t = queryset.first()
        from django.utils.html import escape, format_html
        from .services import safe_activate
        result = safe_activate(t.key, user=request.user)
        if result["ok"]:
            self.message_user(request, f"'{t.name}' is now the active theme.")
            return
        prev = result.get("rolled_back_to") or "previous theme"
        err_id = f"theme-err-{t.pk}"
        self.message_user(request, format_html(
            "Yüklediğin <b>{}</b> temasında sorun çıktı; senin yerine önceki temayı "
            "(<b>{}</b>) yeniden aktif ettim 💜 Hata aşağıda — düzeltip tekrar dene."
            "<details class='mt-2'><summary class='cursor-pointer text-sm'>Hata detayı "
            "(kopyalanabilir)</summary>"
            "<pre id='{}' style='white-space:pre-wrap;max-height:240px;overflow:auto;"
            "padding:10px;border:1px solid rgba(0,0,0,.15);border-radius:8px;"
            "margin-top:6px;font-size:12px;user-select:all'>{}</pre>"
            "<button type='button' class='text-sm underline' "
            "onclick=\"navigator.clipboard.writeText(document.getElementById('{}').innerText)"
            ".then(()=>this.innerText='Kopyalandı ✓')\">Hatayı kopyala</button></details>",
            t.name, prev, err_id, escape(result["error"]), err_id,
        ), level=messages.ERROR)

    def get_urls(self):
        custom = [path("install/", self.admin_site.admin_view(self.install_view),
                       name="themes_installedtheme_install")]
        return custom + super().get_urls()

    def install_view(self, request):
        u = request.user
        if not (u.is_superuser or (u.role_names & {"Developer", "Designer"})):
            raise PermissionDenied
        if request.method == "POST" and request.FILES.get("package"):
            try:
                key = install_theme_zip(request.FILES["package"])
                self.message_user(request, f"Theme '{key}' installed. Use the action to activate it.")
                return redirect("..")
            except ThemeInstallError as e:
                self.message_user(request, str(e), level=messages.ERROR)
        ctx = {**self.admin_site.each_context(request), "title": "Install theme (.zip)",
               "opts": self.model._meta}
        return render(request, "admin/themes/install.html", ctx)

    def has_add_permission(self, request):
        return False
