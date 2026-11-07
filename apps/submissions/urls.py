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

app_name = "submit"

urlpatterns = [
    path("", views.start, name="start"),
    path("quick/", views.quick, name="quick"),
    path("<int:pk>/files/", views.files, name="files"),
    path("<int:pk>/metadata/", views.metadata, name="metadata"),
    path("<int:pk>/authors/", views.authors, name="authors"),
    path("<int:pk>/confirm/", views.confirm, name="confirm"),
    path("<int:pk>/done/", views.done, name="done"),
]
