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

"""Hijack ('Login as') yetki kuralı — yalnız superuser ve Developer rolü."""


def authorize(*, hijacker, hijacked):
    if not (hijacker and hijacker.is_active):
        return False
    if getattr(hijacked, "is_superuser", False) and not hijacker.is_superuser:
        return False
    if hijacker.is_superuser:
        return True
    return hijacker.groups.filter(name="Developer").exists()
