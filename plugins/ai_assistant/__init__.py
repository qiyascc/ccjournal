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

"""
generic plugin: opsiyonel AI editoryal asistan (insan-onaylı öneriler).

Dört yardımcı: desk-check özeti, metadata çıkarımı, hakem raporu sentezi,
hakem kısa listesi. `config.ini [ai] api_key` yoksa veya plugin kapalıysa
arayüzde hiçbir iz bırakmaz. Hiçbir çıktı otomatik uygulanmaz.
"""
from apps.plugins.base import Plugin, PluginCategory
from apps.plugins.hooks import hooks


class AIAssistantPlugin(Plugin):
    key = "ai_assistant"
    name = "AI editorial assistant"
    version = "1.0.0"
    category = PluginCategory.GENERIC
    author = "Qiyas CC"
    description = ("Optional LLM helpers (desk-check, metadata, review "
                   "synthesis, reviewer shortlist). Needs [ai] api_key.")

    def register(self):
        hooks.register("manage.integrity_extra", self.integrity_panels, plugin=self)
        hooks.register("manage.reviews_extra", self.reviews_panels, plugin=self)
        hooks.register("submission.submitted", self.on_submitted, plugin=self)

    def _panel(self, kind, submission, request):
        from django.template.loader import render_to_string

        from . import service
        report = service.get_report(kind, submission.pk)
        return render_to_string("ai_assistant/panel.html", {
            "kind": kind,
            "label": service.KIND_LABELS[kind],
            "report": report,
            "sub": submission,
        }, request=request)

    def integrity_panels(self, html, *, submission, request):
        from . import service
        if not service.configured():
            return html
        return html + "".join(
            self._panel(k, submission, request) for k in ("desk_check", "metadata"))

    def reviews_panels(self, html, *, submission, request):
        from . import service
        if not service.configured():
            return html
        return html + "".join(
            self._panel(k, submission, request) for k in ("synthesis", "rerank"))

    def on_submitted(self, *, submission, **kwargs):
        from . import service
        if not service.active():
            return
        if not self.get_setting("auto_desk_check", True):
            return
        try:
            service.request_run("desk_check", submission)
        except Exception:
            import logging
            logging.getLogger("plugins").exception("ai desk-check enqueue failed")


plugin = AIAssistantPlugin()
