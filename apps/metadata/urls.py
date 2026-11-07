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

app_name = "metadata"

urlpatterns = [
    path("oai", views.oai, name="oai"),
    path("export/crossref", views.crossref_deposit, name="crossref"),
    path("export/doaj", views.doaj_export, name="doaj"),
    path("export/pubmed", views.pubmed_export, name="pubmed"),
]
