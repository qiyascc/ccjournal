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
from rangefilter.filters import DateTimeRangeFilterBuilder

from .models import EmailLog, EmailTemplate, Notification


@admin.register(EmailTemplate)
class EmailTemplateAdmin(ModelAdmin):
    actions = ["action_send_test"]

    @admin.action(description="Send a test of selected template(s) to me")
    def action_send_test(self, request, queryset):
        from django.contrib import messages
        from django.template import Context, Template
        if not request.user.email:
            self.message_user(request, "Your account has no email address.",
                              level=messages.ERROR)
            return
        from .services import NotificationService
        sample = {"title": "Sample Article Title", "journal": "Test render",
                  "note": "This is a sample editorial note.",
                  "due": "2026-12-31", "review_url": "https://example.org/review/x/",
                  "work_url": "https://example.org/work/x/",
                  "issue": "Vol. 1 No. 1 (2026)",
                  "issue_url": "https://example.org/issue/1/",
                  "profile_url": "https://example.org/accounts/profile/",
                  "invite_url": "https://example.org/accounts/invite/x/",
                  "verify_url": "https://example.org/accounts/verify/x/",
                  "role": "Reviewer", "message": "", "toc": "• Sample item",
                  "decision": "Accept", "kind": "copyedit"}
        sent = 0
        for tpl in queryset:
            try:
                subject = Template(tpl.subject).render(Context(sample))
                body = Template(tpl.body).render(Context(sample))
            except Exception as exc:
                self.message_user(request, f"{tpl}: template error — {exc}",
                                  level=messages.ERROR)
                continue
            NotificationService.notify_raw(
                journal=tpl.journal, to=[request.user.email],
                subject=f"[TEST] {subject}", body=body, key="template_test")
            sent += 1
        if sent:
            self.message_user(request, f"Sent {sent} test email(s) to "
                                       f"{request.user.email}.")
    list_display = ("key", "locale", "journal", "enabled")
    list_filter = ("key", "locale", "enabled", "journal")
    search_fields = ("subject", "body")


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ("title", "recipient", "type", "is_read", "created_at")
    list_filter = ("type", "is_read")
    search_fields = ("title", "recipient__email")
    readonly_fields = ("created_at",)


@admin.register(EmailLog)
class EmailLogAdmin(ModelAdmin):
    list_display = ("created_at", "subject", "to_emails", "template_key", "status")
    list_filter = ("status", "template_key", "locale",
                   ("created_at", DateTimeRangeFilterBuilder(title="Sent")))
    search_fields = ("subject", "to_emails", "body")
    date_hierarchy = "created_at"
    readonly_fields = ("journal", "template_key", "locale", "from_email", "to_emails",
                       "subject", "body", "status", "error", "content_type", "object_id",
                       "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
