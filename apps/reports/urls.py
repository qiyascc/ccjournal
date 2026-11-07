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

app_name = "reports"
urlpatterns = [
    path("", views.index, name="index"),
    path("submissions.csv", views.submissions_csv, name="submissions"),
    path("reviews.csv", views.reviews_csv, name="reviews"),
    path("users.csv", views.users_csv, name="users"),
    path("subscriptions.csv", views.subscriptions_csv, name="subscriptions"),
    path("usage/", views.usage, name="usage"),
    path("usage.csv", views.usage_csv, name="usage_csv"),
    path("counter.csv", views.counter_csv, name="counter_csv"),
    path("editorial.csv", views.editorial_csv, name="editorial_csv"),
]
