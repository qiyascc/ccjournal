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

from django.urls import path, reverse
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from .models import PdfTemplate


@admin.register(PdfTemplate)
class PdfTemplateAdmin(ModelAdmin):
    list_display = ("name", "journal", "mode", "page_size", "is_active", "updated_at")
    list_filter = ("journal", "mode", "is_active")
    search_fields = ("name",)
    change_form_template = "admin/publications/pdftemplate/change_form.html"
    fieldsets = (
        (None, {"fields": ("journal", "name", "mode", "is_active")}),
        ("Visual designer", {"fields": ("design",),
         "description": "Use the visual controls below — no code needed. "
                        "Switch ‘Mode’ to Custom HTML/CSS for full control."}),
        ("Custom HTML/CSS (advanced)", {"fields": ("body_html", "css", "page_size"),
         "classes": ("collapse",),
         "description": "Only used when Mode = Custom HTML/CSS. Variables: "
                        "{{ title }}, {{ authors }}, {{ abstract }}, {{ body }}, "
                        "{{ logo_url }}, {{ doi }}, {{ keywords }}, {{ issue_line }} …"}),
    )

    def save_model(self, request, obj, form, change):
        from apps.publications.models import DEFAULT_PDF_DESIGN
        if obj.mode == "visual" and not obj.design:
            obj.design = DEFAULT_PDF_DESIGN
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom = [path("<int:pk>/preview/", self.admin_site.admin_view(self.preview_view),
                       name="publications_pdftemplate_preview")]
        return custom + urls

    def preview_view(self, request, pk):
        """Dergiden örnek bir yayınla canlı PDF; kaydedilmemiş tasarımı da önizler."""
        import json
        from apps.publications.models import Publication
        from apps.publications.pdf import render_pdf_html
        tpl = get_object_or_404(PdfTemplate, pk=pk)
        pub = (Publication.objects.filter(submission__journal=tpl.journal)
               .order_by("-date_published", "-id").first())
        if not pub:
            return HttpResponse(
                "No published article in this journal yet — add one to preview.",
                content_type="text/plain", status=404)
        if request.method == "POST":
            tpl.mode = request.POST.get("mode", tpl.mode)
            raw = request.POST.get("design")
            if raw:
                try:
                    tpl.design = json.loads(raw)
                except (ValueError, TypeError):
                    pass
            tpl.body_html = request.POST.get("body_html", tpl.body_html)
            tpl.css = request.POST.get("css", tpl.css)
        from weasyprint import HTML
        html, _ = render_pdf_html(pub, request=request, template=tpl)
        pdf = HTML(string=html).write_pdf()
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = "inline; filename=preview.pdf"
        return resp

    def change_view(self, request, object_id, form_url="", extra_context=None):
        import json
        from apps.publications.models import DEFAULT_PDF_DESIGN
        extra_context = extra_context or {}
        extra_context["pdf_preview_url"] = reverse(
            "admin:publications_pdftemplate_preview", args=[object_id])
        extra_context["pdf_default_design"] = json.dumps(DEFAULT_PDF_DESIGN)
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url="", extra_context=None):
        """Add sayfasında da tasarımcı tam çalışır (varsayılan design ile);
        canlı önizleme kayıttan sonra aktifleşir."""
        import json
        from apps.publications.models import DEFAULT_PDF_DESIGN
        extra_context = extra_context or {}
        extra_context["pdf_default_design"] = json.dumps(DEFAULT_PDF_DESIGN)
        return super().add_view(request, form_url, extra_context)
