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

"""Şablon bağlamı: ORCID giriş butonu görünürlüğü (config-gated)."""


def orcid(request):
    from .orcid_sso import is_configured
    return {"orcid_enabled": is_configured()}
