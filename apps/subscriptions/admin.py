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
from rangefilter.filters import DateTimeRangeFilterBuilder, DateRangeFilterBuilder

from .models import Payment, Subscription, SubscriptionType


@admin.register(SubscriptionType)
class SubscriptionTypeAdmin(ModelAdmin):
    list_display = ("name", "is_institutional", "duration_months", "price", "currency", "is_active")
    list_filter = ("is_institutional", "is_active", "currency")
    search_fields = ("name", "description")


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ("__str__", "type", "status", "date_start", "date_end", "is_current_disp")
    list_filter = ("status", "type", "type__is_institutional",
                   ("date_end", DateRangeFilterBuilder(title="Ends")))
    search_fields = ("user__email", "user__given_name", "user__family_name", "institution_name")
    autocomplete_fields = ("user", "type")
    date_hierarchy = "date_end"

    @admin.display(description="Current", boolean=True)
    def is_current_disp(self, obj):
        return obj.is_current


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ("__str__", "subscription", "amount", "currency", "status", "paid_at")
    list_filter = ("status", "currency", "method",
                   ("created_at", DateTimeRangeFilterBuilder(title="Created")))
    search_fields = ("note", "subscription__user__email")
    autocomplete_fields = ("subscription",)
    date_hierarchy = "created_at"
