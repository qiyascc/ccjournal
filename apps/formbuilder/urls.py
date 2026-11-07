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

from . import views

app_name = "formbuilder"
urlpatterns = [
    path("", views.form_home, name="home"),
    path("<slug:slug>/", views.form_detail, name="detail"),
    path("<slug:slug>/done/", views.form_done, name="done"),
]
