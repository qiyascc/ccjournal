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

from django.urls import path

from . import public_views as v

app_name = "review_public"
urlpatterns = [
    path("<str:token>/", v.landing, name="landing"),
    path("<str:token>/form/", v.form, name="form"),
    path("<str:token>/done/", v.done, name="done"),
    path("<str:token>/file/<int:file_id>/", v.file_download, name="file"),
    path("<str:token>/certificate.pdf", v.certificate, name="certificate"),
]
