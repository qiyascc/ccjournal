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

"""User.groups değişince admin erişimini (is_staff) senkronla + giriş kısıtlama sayaçları."""
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from .models import User


@receiver(m2m_changed, sender=User.groups.through)
def sync_staff_on_group_change(sender, instance, action, **kwargs):
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if isinstance(instance, User):
        instance.sync_staff()


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    if request is None:
        return
    from . import throttle
    throttle.register_failure(request, credentials.get("username", ""))


@receiver(user_logged_in)
def on_login_success(sender, request, user, **kwargs):
    if request is None:
        return
    from . import throttle
    throttle.reset(request, getattr(user, "email", ""))
