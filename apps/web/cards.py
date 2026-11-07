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

"""OG sosyal medya kartı — makale başına otomatik 1200×630 PNG (Pillow).

Paylaşılan her makale linki profesyonel bir kartla açılır; harici servis yok.
Kart medya altında önbelleğe alınır; başlık değişirse (içerik hash'i) yeniden çizilir.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from apps.submissions.models import Submission, SubmissionStatus

from .views import _content_locale, _journal_or_404

W, H = 1200, 630
PAPER, INK, SOFT, ACCENT = "#f7f5ef", "#1c1917", "#6b6459", "#b3542e"

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]


def _font(size, bold=True):
    from PIL import ImageFont
    for p in (_FONT_CANDIDATES if bold else _FONT_REG):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        probe = f"{cur} {w}".strip()
        if draw.textlength(probe, font=font) <= max_w:
            cur = probe
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_card(title: str, journal_title: str, authors: str, doi: str) -> bytes:
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 14], fill=ACCENT)
    d.text((70, 56), journal_title.upper()[:60], font=_font(30, bold=False), fill=ACCENT)

    tf = _font(64)
    lines = _wrap(d, title, tf, W - 140)[:4]
    if len(lines) == 4:
        lines[3] += " …"
    y = 130
    for ln in lines:
        d.text((70, y), ln, font=tf, fill=INK)
        y += 78

    if authors:
        d.text((70, min(y + 18, H - 130)), authors[:110],
               font=_font(32, bold=False), fill=SOFT)
    footer = f"doi.org/{doi}" if doi else "Open access · Peer reviewed"
    d.text((70, H - 70), footer, font=_font(26, bold=False), fill=ACCENT)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def article_card(request, pk):
    journal = _journal_or_404()
    submission = get_object_or_404(
        Submission, pk=pk, journal=journal, status=SubmissionStatus.PUBLISHED)
    pub = submission.current_publication
    if not pub:
        raise Http404
    loc = _content_locale(request, journal)
    t = pub.tr(loc) or pub.translations.first()
    jt = journal.tr(loc)
    title = (t.title if t else f"Article #{pk}")
    jname = (jt.title if jt else journal.path)
    authors = ", ".join(f"{a.given_name} {a.family_name}".strip()
                        for a in pub.authors.order_by("seq")[:4])
    doi = pub.doi.doi if pub.doi_id else ""

    key = hashlib.sha1(f"{title}|{jname}|{authors}|{doi}".encode()).hexdigest()[:12]
    from django.conf import settings
    cache_dir = Path(settings.MEDIA_ROOT) / "cards"
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"article-{pk}-{key}.png"
    if not path.exists():
        path.write_bytes(render_card(title, jname, authors, doi))
    resp = FileResponse(path.open("rb"), content_type="image/png")
    resp["Cache-Control"] = "public, max-age=86400"
    return resp
