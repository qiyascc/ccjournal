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

"""Form builder admini — form + alan inline (sıralı), başvurular + onay/reddetme aksiyonları."""
from django.contrib import admin, messages
from django.utils.html import format_html
from rangefilter.filters import DateTimeRangeFilterBuilder
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action as unfold_action

from .models import Form, FormField, FormSubmission, SubmissionStatus, SubmissionUpload
from .services import FormService


class FormFieldInline(TabularInline):
    model = FormField
    extra = 0
    fields = ("seq", "label", "slug", "field_type", "required", "help_text",
              "placeholder", "choices", "is_active")
    ordering = ("seq",)
    prepopulated_fields = {"slug": ("label",)}


@admin.register(Form)
class FormAdmin(ModelAdmin):
    list_display = ("title", "slug", "is_active", "entry_count", "seq", "is_protected")
    list_editable = ("is_active", "seq")
    search_fields = ("title", "slug")
    inlines = [FormFieldInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "description", "is_active", "seq")}),
        ("Behaviour", {"fields": ("success_message", "notify_submitter", "is_protected")}),
    )

    @admin.display(description="Entries")
    def entry_count(self, obj):
        return obj.entries.count()

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_protected:
            return False
        return super().has_delete_permission(request, obj)


class SubmissionUploadInline(TabularInline):
    model = SubmissionUpload
    extra = 0
    can_delete = False
    readonly_fields = ("field_slug", "file", "original_name", "uploaded_at")


@admin.register(FormSubmission)
class FormSubmissionAdmin(ModelAdmin):
    list_display = ("__str__", "form", "status_badge", "submitter_email",
                    "created_at", "decided_by")
    list_filter = ("form", "status",
                   ("created_at", DateTimeRangeFilterBuilder(title="Received")))
    search_fields = ("submitter_email", "submitter_name", "data")
    readonly_fields = ("form", "data_table", "submitter_email", "submitter_name",
                       "locale", "decided_by", "decided_at", "created_at")
    exclude = ("data",)
    inlines = [SubmissionUploadInline]
    actions = ["approve_selected", "reject_selected"]
    actions_detail = ["approve_one", "reject_one"]

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {1: "#6b7280", 2: "#16a34a", 3: "#dc2626"}
        return format_html('<b style="color:{}">{}</b>',
                           colors.get(obj.status, "#000"), obj.get_status_display())

    @admin.display(description="Submitted data")
    def data_table(self, obj):
        from django.utils.html import escape
        from django.utils.safestring import mark_safe
        labels = {f.slug: f.label for f in obj.form.fields.all()}
        rows = "".join(
            f"<tr><td style='padding:4px 14px 4px 0;color:#666;white-space:nowrap'>"
            f"{escape(labels.get(k, k))}</td>"
            f"<td style='padding:4px 0'>{escape(v)}</td></tr>"
            for k, v in obj.data.items())
        return mark_safe(f"<table>{rows}</table>") if rows else "—"

    def _can_decide(self, request):
        return request.user.has_perm("formbuilder.decide_formsubmission") or \
            request.user.is_superuser

    @admin.action(description="Approve (advance) selected")
    def approve_selected(self, request, queryset):
        if not self._can_decide(request):
            self.message_user(request, "You lack the decide permission.", messages.ERROR)
            return
        n = sum(1 for e in queryset
                if FormService.set_status(e, SubmissionStatus.APPROVED, request.user))
        self.message_user(request, f"{n} submission(s) approved; submitters notified.")

    @admin.action(description="Reject selected (files kept in /reject/)")
    def reject_selected(self, request, queryset):
        if not self._can_decide(request):
            self.message_user(request, "You lack the decide permission.", messages.ERROR)
            return
        n = sum(1 for e in queryset
                if FormService.set_status(e, SubmissionStatus.REJECTED, request.user))
        self.message_user(request, f"{n} submission(s) rejected; files archived under media/reject/.")

    @unfold_action(description="Approve / advance")
    def approve_one(self, request, object_id):
        from django.shortcuts import redirect
        if self._can_decide(request):
            FormService.set_status(FormSubmission.objects.get(pk=object_id),
                                   SubmissionStatus.APPROVED, request.user)
            messages.success(request, "Approved; submitter notified by email.")
        else:
            messages.error(request, "You lack the decide permission.")
        return redirect("admin:formbuilder_formsubmission_change", object_id)

    @unfold_action(description="Reject")
    def reject_one(self, request, object_id):
        from django.shortcuts import redirect
        if self._can_decide(request):
            FormService.set_status(FormSubmission.objects.get(pk=object_id),
                                   SubmissionStatus.REJECTED, request.user)
            messages.success(request, "Rejected; files archived, submitter notified.")
        else:
            messages.error(request, "You lack the decide permission.")
        return redirect("admin:formbuilder_formsubmission_change", object_id)

    def has_add_permission(self, request):
        return False
