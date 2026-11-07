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
from apps.accounts.scoping import ScopedAdminMixin
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    Appeal, Discussion, DiscussionMessage, EditorialDecision, ReviewAssignment,
    ReviewerProfile, ReviewFormItem, ReviewFormTemplate, ReviewInterest,
    ReviewRound, StageAssignment,
)


@admin.register(Appeal)
class AppealAdmin(ModelAdmin):
    list_display = ("submission", "status", "created_at", "decided_by", "decided_at")
    list_filter = ("status",)
    readonly_fields = ("submission", "reason", "created_at", "decided_by",
                       "decided_at")
    autocomplete_fields = ()

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data \
                and obj.status != Appeal.Status.OPEN:
            from django.utils import timezone
            obj.decided_by = request.user
            obj.decided_at = timezone.now()
        super().save_model(request, obj, form, change)


class ReviewFormItemInline(TabularInline):
    model = ReviewFormItem
    extra = 1
    tab = True
    fields = ("seq", "label", "kind", "choices", "required", "help_text")


@admin.register(ReviewFormTemplate)
class ReviewFormTemplateAdmin(ModelAdmin):
    inlines = [ReviewFormItemInline]
    list_display = ("title", "journal", "is_active", "item_count", "created_at")
    list_filter = ("journal", "is_active")

    @admin.display(description="Questions")
    def item_count(self, obj):
        return obj.items.count()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.is_active:
            (ReviewFormTemplate.objects.filter(journal=obj.journal, is_active=True)
             .exclude(pk=obj.pk).update(is_active=False))


class ReviewAssignmentInline(TabularInline):
    model = ReviewAssignment
    extra = 0
    tab = True
    fields = ("reviewer", "review_mode", "date_due", "recommendation", "date_completed")
    autocomplete_fields = ("reviewer",)


@admin.register(ReviewRound)
class ReviewRoundAdmin(ScopedAdminMixin, ModelAdmin):
    submission_path = "submission"
    inlines = [ReviewAssignmentInline]
    list_display = ("submission", "stage", "round", "status")
    list_filter = ("stage", "status")
    search_fields = ("submission__id",)
    autocomplete_fields = ("submission",)


@admin.register(EditorialDecision)
class EditorialDecisionAdmin(ScopedAdminMixin, ModelAdmin):
    submission_path = "submission"
    list_display = ("submission", "stage", "decision", "editor", "created_at")
    list_filter = ("stage", "decision")
    autocomplete_fields = ("submission", "editor")


@admin.register(StageAssignment)
class StageAssignmentAdmin(ScopedAdminMixin, ModelAdmin):
    submission_path = "submission"
    list_display = ("submission", "user", "role", "is_recommend_only")
    autocomplete_fields = ("submission", "user")


class DiscussionMessageInline(TabularInline):
    model = DiscussionMessage
    extra = 1
    tab = True


@admin.register(Discussion)
class DiscussionAdmin(ScopedAdminMixin, ModelAdmin):
    submission_path = "submission"
    inlines = [DiscussionMessageInline]
    list_display = ("subject", "submission", "stage", "closed", "created_at")
    list_filter = ("stage", "closed")
    autocomplete_fields = ("submission",)


@admin.register(ReviewAssignment)
class ReviewAssignmentAdmin(ScopedAdminMixin, ModelAdmin):
    submission_path = "review_round__submission"
    list_display = ("reviewer", "review_round", "recommendation", "date_due", "date_completed")
    list_filter = ("recommendation", "date_due")
    search_fields = ("reviewer__email", "reviewer__given_name", "reviewer__family_name")
    autocomplete_fields = ("review_round", "reviewer")
    exclude = ("form_responses",)
    readonly_fields = ("form_responses_display",)

    @admin.display(description="Review form responses")
    def form_responses_display(self, obj):
        from django.utils.html import format_html, format_html_join
        rows = obj.form_responses or []
        if not rows:
            return "—"
        def _val(v):
            return ", ".join(v) if isinstance(v, list) else v
        return format_html(
            "<dl style='margin:0'>{}</dl>",
            format_html_join(
                "", "<dt style='font-weight:600;margin-top:.5em'>{}</dt><dd>{}</dd>",
                ((r.get("label", ""), _val(r.get("value", ""))) for r in rows)))


@admin.register(ReviewInterest)
class ReviewInterestAdmin(ModelAdmin):
    list_display = ("name", "reviewer_count")
    search_fields = ("name",)

    @admin.display(description="Reviewers")
    def reviewer_count(self, obj):
        return obj.reviewers.count()


@admin.register(ReviewerProfile)
class ReviewerProfileAdmin(ModelAdmin):
    list_display = ("user", "interest_list", "is_available", "public_listing",
                    "n_assigned", "n_completed", "n_declined", "avg_quality_disp",
                    "avg_days_disp")
    list_filter = ("is_available", "public_listing", "interests")
    search_fields = ("user__email", "user__given_name", "user__family_name",
                     "affiliation", "expertise", "interests__name")
    autocomplete_fields = ("user",)
    filter_horizontal = ("interests",)
    actions = ["action_year_summary"]

    @admin.action(description="Send last year's summary email to selected reviewers")
    def action_year_summary(self, request, queryset):
        from django.contrib import messages
        from django.utils import timezone

        from .certificates import send_year_summary
        year = timezone.now().year - 1
        sent = sum(1 for p in queryset.select_related("user")
                   if send_year_summary(p.user, year))
        skipped = queryset.count() - sent
        msg = f"Sent {sent} summary email(s) for {year}."
        if skipped:
            msg += f" {skipped} skipped (no completed reviews or no email)."
        self.message_user(request, msg,
                          level=messages.WARNING if skipped else messages.INFO)

    def get_queryset(self, request):
        from django.db.models import Avg, Count, Q
        return (super().get_queryset(request)
                .select_related("user").prefetch_related("interests", "user__review_assignments")
                .annotate(
                    _assigned=Count("user__review_assignments", distinct=True),
                    _completed=Count("user__review_assignments",
                        filter=Q(user__review_assignments__date_completed__isnull=False),
                        distinct=True),
                    _declined=Count("user__review_assignments",
                        filter=Q(user__review_assignments__declined=True), distinct=True),
                    _quality=Avg("user__review_assignments__quality")))

    @admin.display(description="Interests")
    def interest_list(self, obj):
        return ", ".join(i.name for i in obj.interests.all()) or "—"

    @admin.display(description="Assigned", ordering="_assigned")
    def n_assigned(self, obj):
        return obj._assigned

    @admin.display(description="Completed", ordering="_completed")
    def n_completed(self, obj):
        return obj._completed

    @admin.display(description="Declined", ordering="_declined")
    def n_declined(self, obj):
        return obj._declined

    @admin.display(description="Avg quality", ordering="_quality")
    def avg_quality_disp(self, obj):
        return round(obj._quality, 1) if obj._quality is not None else "—"

    @admin.display(description="Avg days")
    def avg_days_disp(self, obj):
        d = obj.avg_days
        return d if d is not None else "—"
