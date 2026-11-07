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

"""DOCX/manuscript → temiz HTML (CKEditor gövdesi için).

Yazar zaten .docx yükler; bunu elle kopyalamak yerine `mammoth` ile semantik
HTML'e çevirir (başlıklar, paragraflar, listeler, kalın/italik, dipnotlar,
gömülü görseller base64). Çıktı PublicationTranslation.body'ye yazılır ve
editör CKEditor'da düzeltir.
"""
from __future__ import annotations

import re

_STYLE_MAP = """
p[style-name='Title'] => h1:fresh
p[style-name='Subtitle'] => p.subtitle:fresh
p[style-name='Heading 1'] => h2:fresh
p[style-name='Heading 2'] => h3:fresh
p[style-name='Heading 3'] => h4:fresh
p[style-name='Başlık 1'] => h2:fresh
p[style-name='Başlık 2'] => h3:fresh
p[style-name='Quote'] => blockquote:fresh
p[style-name='Intense Quote'] => blockquote:fresh
p[style-name='Abstract'] => p.abstract:fresh
r[style-name='Strong'] => strong
r[style-name='Emphasis'] => em
"""


def _clean(html: str) -> str:
    """mammoth çıktısını yayına hazır, sağlam HTML'e dönüştürür.

    - boş paragrafları siler, fazla boşlukları kısar
    - tabloları sarmalar (yatay kaydırma) ve sınıf verir; ilk satırı başlık (<th>) yapar
    - görselleri taşmayı önleyecek sınıfla işaretler
    Böylece görselli/tablolu belgeler hem editörde hem PDF'te düzgün görünür.
    """
    if not html:
        return ""
    html = re.sub(r"<p>\s*(&nbsp;)?\s*</p>", "", html)

    def _fix_table(m):
        inner = m.group(1)
        first_row = re.search(r"<tr>(.*?)</tr>", inner, re.DOTALL)
        if first_row:
            head = first_row.group(0)
            head_th = head.replace("<td>", "<th>").replace("</td>", "</th>")
            inner = inner.replace(head, head_th, 1)
        return ('<div class="cc-table-wrap"><table class="cc-table">'
                + inner + "</table></div>")
    html = re.sub(r"<table>(.*?)</table>", _fix_table, html, flags=re.DOTALL)

    def _fix_img(m):
        tag = m.group(0)
        if "class=" not in tag:
            tag = tag.replace("<img ", '<img class="cc-figure-img" ')
        return tag
    html = re.sub(r"<img\b[^>]*>", _fix_img, html)

    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def docx_to_html(fileobj) -> tuple[str, list[str]]:
    """Bir .docx dosya nesnesini (HTML, uyarılar) olarak döndürür.

    Görseller veri-URI (base64) olarak gömülür; harici dosya gerektirmez. Tek bir
    görsel başarısız olsa bile parse çökmez; tüm dönüşüm patlarsa görseller olmadan
    yeniden denenir.
    """
    import mammoth
    try:
        result = mammoth.convert_to_html(
            fileobj,
            style_map=_STYLE_MAP,
            convert_image=mammoth.images.img_element(_inline_image),
        )
        return _clean(result.value), [m.message for m in result.messages]
    except Exception as exc:  # noqa: BLE001
        try:
            fileobj.seek(0)
        except Exception:
            pass
        try:
            result = mammoth.convert_to_html(fileobj, style_map=_STYLE_MAP)
            return _clean(result.value), [
                "Images could not be embedded and were skipped: %s" % exc]
        except Exception as exc2:  # noqa: BLE001
            return "", [f"Could not parse the document: {exc2}"]


def _inline_image(image):
    import base64
    try:
        with image.open() as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return {"src": f"data:{image.content_type};base64,{data}",
                "class": "cc-figure-img"}
    except Exception:
        return {"src": "", "alt": "image could not be embedded"}


_BODY_SOURCE_STAGES = [15, 9, 11, 2]


def find_manuscript_file(submission):
    """Gövdeye çevrilecek en uygun dosyayı bulur (en güncel aşama önce).

    .docx tercih edilir; yoksa en güncel manuscript dosyası döner ki çağıran
    taraf "Word değil" gibi anlaşılır bir mesaj verebilsin.
    """
    files = list(submission.files.order_by("-created_at"))
    if not files:
        return None
    docx = [f for f in files if (f.original_filename or "").lower().endswith(".docx")]
    by_stage = {}
    for f in (docx or files):
        by_stage.setdefault(f.file_stage, f)
    for stage in _BODY_SOURCE_STAGES:
        if stage in by_stage:
            return by_stage[stage]
    return (docx or files)[0]


def import_body_from_manuscript(publication, *, locale=None, overwrite=False):
    """Yayının gönderi dosyasından gövdeyi parse edip PublicationTranslation.body'ye yazar.

    Dönüş: (translation, warnings) veya (None, ["sebep"]).
    .docx değilse veya dosya yoksa boş gövdeyle döner.
    """
    from .models import PublicationTranslation
    submission = publication.submission
    sf = find_manuscript_file(submission)
    if not sf:
        return None, ["No manuscript file found on the submission."]
    name = (sf.original_filename or "").lower()
    if not name.endswith((".docx", ".doc")):
        return None, [f"Manuscript “{sf.original_filename}” is not a Word file; "
                      "only .docx can be auto-parsed."]
    if name.endswith(".doc"):
        return None, ["Legacy .doc is not supported; please upload .docx."]

    loc = locale or publication.primary_locale
    t, _ = PublicationTranslation.objects.get_or_create(
        publication=publication, locale=loc)
    if t.body and not overwrite:
        return t, ["Body already present; not overwritten (use overwrite)."]

    with sf.file.open("rb") as fh:
        html, warnings = docx_to_html(fh)
    t.body = html
    t.save(update_fields=["body"])
    return t, warnings
