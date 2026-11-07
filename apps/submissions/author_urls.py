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

from . import author_views as v

app_name = "author_work"
urlpatterns = [
    path("<str:token>/package.zip", v.package_download, name="package"),
    path("<str:token>/credit/<str:atoken>/", v.credit_approval, name="credit"),
    path("<str:token>/appeal/", v.appeal, name="appeal"),
    path("<str:token>/", v.landing, name="landing"),
    path("<str:token>/upload/", v.upload, name="upload"),
]
