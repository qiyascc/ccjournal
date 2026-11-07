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

"""Abonelik + ödeme (OJS subscriptions) — paywall waffle 'subscriptions' anahtarı ardında."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class SubscriptionType(TimeStampedModel):
    journal = models.ForeignKey("journals.Journal", on_delete=models.CASCADE,
                                related_name="subscription_types")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    duration_months = models.PositiveIntegerField(default=12)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="AZN")
    is_institutional = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["is_institutional", "name"]
        verbose_name = "Subscription type"

    def __str__(self) -> str:
        kind = "Institutional" if self.is_institutional else "Individual"
        return f"{self.name} ({kind}, {self.price} {self.currency})"


class Subscription(TimeStampedModel):
    class Status(models.IntegerChoices):
        PENDING = 1, "Pending"
        ACTIVE = 2, "Active"
        EXPIRED = 3, "Expired"
        CANCELLED = 4, "Cancelled"

    journal = models.ForeignKey("journals.Journal", on_delete=models.CASCADE,
                                related_name="subscriptions")
    type = models.ForeignKey(SubscriptionType, on_delete=models.PROTECT, related_name="subscriptions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="subscriptions")
    institution_name = models.CharField(max_length=255, blank=True)
    date_start = models.DateField(default=timezone.localdate)
    date_end = models.DateField()
    status = models.IntegerField(choices=Status.choices, default=Status.ACTIVE, db_index=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_end"]
        verbose_name = "Subscription"

    def __str__(self) -> str:
        who = self.user or self.institution_name or "?"
        return f"{who} · {self.type.name}"

    @property
    def is_current(self) -> bool:
        return self.status == self.Status.ACTIVE and self.date_end >= timezone.localdate()


class Payment(TimeStampedModel):
    class Status(models.IntegerChoices):
        PENDING = 1, "Pending"
        PAID = 2, "Paid"
        REFUNDED = 3, "Refunded"
        FAILED = 4, "Failed"

    journal = models.ForeignKey("journals.Journal", on_delete=models.CASCADE,
                                related_name="payments")
    subscription = models.ForeignKey(Subscription, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="AZN")
    method = models.CharField(max_length=40, blank=True, help_text="manual, card, bank ...")
    status = models.IntegerField(choices=Status.choices, default=Status.PENDING, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment"

    def __str__(self) -> str:
        return f"{self.amount} {self.currency} · {self.get_status_display()}"
