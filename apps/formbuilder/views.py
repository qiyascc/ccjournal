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

"""Form vitrini — kart listesi, form sayfası, başarı sayfası."""
from django.shortcuts import get_object_or_404, redirect, render

from apps.web.views import _base_ctx, _journal_or_404

from .models import Form
from .services import FormService, build_django_form


def form_home(request):
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    ctx["forms"] = Form.objects.filter(is_active=True)
    return render(request, "formbuilder/home.html", ctx)


def form_detail(request, slug):
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    form_obj = get_object_or_404(Form, slug=slug, is_active=True)
    DynForm = build_django_form(form_obj, journal)
    if request.method == "POST":
        dform = DynForm(request.POST, request.FILES)
        if dform.is_valid():
            FormService.save_entry(form_obj, dform.cleaned_data, request.FILES,
                                   locale=ctx.get("cloc", ""))
            return redirect("formbuilder:done", slug=form_obj.slug)
    else:
        dform = DynForm()
    ctx.update({"form_obj": form_obj, "dform": dform})
    return render(request, "formbuilder/form.html", ctx)


def form_done(request, slug):
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    ctx["form_obj"] = get_object_or_404(Form, slug=slug)
    return render(request, "formbuilder/done.html", ctx)
