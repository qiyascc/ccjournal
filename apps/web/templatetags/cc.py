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

"""Vitrin şablon yardımcıları."""
from django import template

register = template.Library()


@register.filter
def tr(obj, locale):
    """Çevrilebilir bir nesnenin verilen locale'deki çeviri satırını döndürür."""
    if obj is None:
        return None
    return obj.tr(locale)


@register.filter
def author_name(a):
    return f"{a.given_name} {a.family_name}".strip()


@register.simple_tag
def cite_apa(pub, locale):
    """Basit APA-benzeri atıf dizgisi."""
    authors = list(pub.authors.all().order_by("seq"))
    names = []
    for a in authors:
        initials = " ".join(p[0] + "." for p in a.given_name.split() if p)
        names.append(f"{a.family_name}, {initials}".strip(", "))
    author_str = ", ".join(names) if names else ""
    year = pub.date_published.year if pub.date_published else "n.d."
    t = pub.tr(locale)
    title = t.title if t else ""
    journal = pub.submission.journal
    jt = journal.tr(locale)
    jname = jt.title if jt else journal.path
    bits = [b for b in [author_str, f"({year}).", f"{title}.", f"{jname}."] if b]
    s = " ".join(bits)
    if pub.issue and pub.issue.volume:
        vol = f"{pub.issue.volume}"
        if pub.issue.number:
            vol += f"({pub.issue.number})"
        s += f" {vol}."
    if pub.pages:
        s += f" {pub.pages}."
    if pub.doi_id:
        s += f" https://doi.org/{pub.doi.doi}"
    return s
