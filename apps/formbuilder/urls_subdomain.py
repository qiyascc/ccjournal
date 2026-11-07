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

"""form.<domain> urlconf'u — kökte form vitrini; ana site rotaları (admin dahil) korunur."""
from django.urls import include, path

import config.urls as main

urlpatterns = [
    path("", include("apps.formbuilder.urls")),
] + main.urlpatterns
