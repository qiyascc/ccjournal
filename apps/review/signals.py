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

"""Kullanıcı 'Reviewer' rolüne eklenince hakem profili oluştur."""
from django.contrib.auth.models import Group
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from apps.accounts.models import User


@receiver(m2m_changed, sender=User.groups.through)
def ensure_reviewer_profile(sender, instance, action, pk_set, **kwargs):
    if action != "post_add" or not isinstance(instance, User):
        return
    names = set(Group.objects.filter(pk__in=(pk_set or [])).values_list("name", flat=True))
    if "Reviewer" in names:
        from .services import ReviewerService
        ReviewerService.ensure_profile(instance)
