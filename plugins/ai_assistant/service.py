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

"""AI asistan çekirdeği — Anthropic Messages API, stdlib urllib ile.

Tamamı öneri üretir; hiçbir çıktı kendiliğinden uygulanmaz. Anahtar yoksa
(`config.ini [ai] api_key`) veya plugin kapalıysa hiçbir iz bırakmaz.
Çağrılar iş kuyruğuna yazılır; periyodik nabız (run_due) boşaltır — istek
hiç bloklanmaz. Raporlar PluginSetting satırlarında saklanır (tablo yok).
"""
from __future__ import annotations

import json
import re
import urllib.request

from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags

KEY = "ai_assistant"
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
BODY_CHARS = 16000

KINDS = ("desk_check", "metadata", "synthesis", "rerank")

KIND_LABELS = {
    "desk_check": "Desk-check summary",
    "metadata": "Metadata extraction",
    "synthesis": "Review synthesis",
    "rerank": "Reviewer shortlist",
}

LOCALE_NAMES = {"en": "English", "tr": "Turkish", "az": "Azerbaijani",
                "ru": "Russian", "de": "German", "fr": "French"}


def configured() -> bool:
    return bool(getattr(settings, "AI_API_KEY", ""))


def active() -> bool:
    if not configured():
        return False
    from apps.plugins.registry import registry
    return registry.is_enabled(KEY)


def _setting(key: str, default=None):
    from apps.plugins.models import PluginSetting
    row = (PluginSetting.objects
           .filter(plugin_key=KEY, journal=None, key=key)
           .values_list("value", flat=True).first())
    return default if row is None else row


def model_name() -> str:
    return _setting("model") or getattr(settings, "AI_MODEL", "") or DEFAULT_MODEL


def _call(system: str, prompt: str, *, max_tokens: int = 1200) -> tuple[str, dict]:
    payload = json.dumps({
        "model": model_name(),
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=payload, headers={
        "x-api-key": settings.AI_API_KEY,
        "anthropic-version": API_VERSION,
        "content-type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = "".join(b.get("text", "") for b in data.get("content", []))
    usage = data.get("usage") or {}
    return text.strip(), {"model": data.get("model", model_name()),
                          "tokens_in": usage.get("input_tokens"),
                          "tokens_out": usage.get("output_tokens")}


def get_report(kind: str, submission_id: int) -> dict | None:
    return _setting(f"report:{kind}:{submission_id}")


def _store(kind: str, submission_id: int, payload: dict) -> None:
    from apps.plugins.models import PluginSetting
    payload = {"at": timezone.now().isoformat(timespec="seconds"), **payload}
    PluginSetting.objects.update_or_create(
        plugin_key=KEY, journal=None, key=f"report:{kind}:{submission_id}",
        defaults={"value": payload})


def request_run(kind: str, submission) -> None:
    from apps.tasks.queue import enqueue
    _store(kind, submission.pk, {"status": "pending"})
    enqueue("plugins.ai_assistant.service.run_job", kind, submission.pk,
            max_attempts=2, queue="ai")


def run_job(kind: str, submission_id: int):
    from apps.submissions.models import Submission
    sub = Submission.objects.select_related(
        "current_publication", "journal").get(pk=submission_id)
    try:
        result = _RUNNERS[kind](sub)
    except Exception as exc:
        _store(kind, submission_id, {"status": "error", "error": str(exc)[:500]})
        raise
    _store(kind, submission_id, {"status": "ok", **result})
    return result


def _system(journal) -> str:
    jt = journal.tr() if journal else None
    name = (jt.title if jt else "") or "the journal"
    loc = (journal.primary_locale if journal else "en") or "en"
    lang = LOCALE_NAMES.get(loc, loc)
    return (f"You are an editorial assistant for the academic journal “{name}”. "
            f"Respond in {lang}. Be concise and factual. You only produce "
            "suggestions for human editors; never present them as decisions.")


def _pub_meta(sub) -> str:
    pub = sub.current_publication
    if not pub:
        return ""
    t = pub.tr(pub.primary_locale)
    kws = ", ".join(k.term for k in pub.keywords.all()[:12])
    parts = [f"Title: {t.title if t else ''}",
             f"Abstract: {strip_tags((t.abstract if t else '') or '')[:2500]}"]
    if kws:
        parts.append(f"Keywords: {kws}")
    if pub.data_availability:
        parts.append(f"Data availability statement: {pub.data_availability[:400]}")
    if pub.ai_statement:
        parts.append(f"AI use declaration: {pub.ai_statement[:400]}")
    return "\n".join(parts)


def _manuscript_text(sub, limit: int = BODY_CHARS) -> str:
    pub = sub.current_publication
    body = ""
    if pub:
        t = pub.tr(pub.primary_locale)
        body = strip_tags((t.body if t else "") or "")
    if len(body) < 200:
        try:
            from apps.publications.docx_import import (
                docx_to_html, find_manuscript_file,
            )
            f = find_manuscript_file(sub)
            if f and f.file:
                with f.file.open("rb") as fh:
                    html, _ = docx_to_html(fh)
                body = strip_tags(html)
        except Exception:
            pass
    return re.sub(r"\s+", " ", body)[:limit]


def _scope(journal) -> str:
    jt = journal.tr() if journal else None
    lines = [f"Journal: {(jt.title if jt else '') or ''}"]
    desc = (jt.description if jt and getattr(jt, "description", "") else "")
    if desc:
        lines.append(f"Scope: {strip_tags(desc)[:800]}")
    sections = ", ".join(str(s) for s in journal.sections.all()[:12]) if journal else ""
    if sections:
        lines.append(f"Sections: {sections}")
    return "\n".join(lines)


def _desk_check(sub) -> dict:
    prompt = (
        f"{_scope(sub.journal)}\n\nNew submission:\n{_pub_meta(sub)}\n\n"
        f"Manuscript text (may be truncated):\n{_manuscript_text(sub, 8000)}\n\n"
        "Write a desk-check briefing for the handling editor with exactly these "
        "sections:\n1. Scope fit (one short paragraph)\n2. Missing or weak items "
        "(bullet list: abstract, keywords, statements, references…)\n3. Language "
        "quality (one short paragraph)\n4. Signals to double-check (bullet list; "
        "write 'none' if none). Do not recommend accept/reject.")
    text, meta = _call(_system(sub.journal), prompt, max_tokens=900)
    return {"text": text, **meta}


def _metadata(sub) -> dict:
    body = _manuscript_text(sub)
    if len(body) < 200:
        raise ValueError("No manuscript text available to extract from.")
    prompt = (
        "Extract bibliographic metadata from this manuscript. Reply with STRICT "
        "JSON only — no prose, no code fences — exactly this shape: "
        '{"title": str, "abstract": str, "keywords": [str, ...]} '
        "(max 6 keywords, keep the document's own language).\n\n"
        f"Manuscript:\n{body}")
    text, meta = _call(_system(sub.journal), prompt, max_tokens=1000)
    raw = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    data = json.loads(raw)
    clean = {"title": str(data.get("title", ""))[:500],
             "abstract": str(data.get("abstract", ""))[:5000],
             "keywords": [str(k)[:80] for k in (data.get("keywords") or [])][:6]}
    return {"data": clean, **meta}


def _synthesis(sub) -> dict:
    from apps.review.models import ReviewAssignment
    done = list(ReviewAssignment.objects.filter(
        review_round__submission=sub, date_completed__isnull=False)
        .order_by("date_completed"))
    if not done:
        raise ValueError("No completed reviews to synthesize.")
    blocks = []
    for i, a in enumerate(done, 1):
        rows = "\n".join(
            f"  {r.get('label', '')}: "
            f"{', '.join(v) if isinstance(v := r.get('value', ''), list) else v}"
            for r in (a.form_responses or []))
        blocks.append(
            f"Reviewer {i} — recommendation: "
            f"{a.get_recommendation_display() if a.recommendation else 'n/a'}\n"
            f"Comments for the author: {a.comments_for_author or '—'}\n"
            f"Confidential comments for the editor: {a.comments_for_editor or '—'}\n"
            f"{rows}")
    prompt = (
        f"Submission:\n{_pub_meta(sub)}\n\nCompleted reviews:\n\n"
        + "\n\n".join(blocks) +
        "\n\nWrite a comparative synthesis for the editor with sections: "
        "1. Where reviewers agree; 2. Where they disagree; 3. Concrete revision "
        "requests (merged, deduplicated bullet list); 4. Options for the editor "
        "(neutral, e.g. 'minor revision if X is addressed'). Never invent "
        "content not present in the reviews.")
    text, meta = _call(_system(sub.journal), prompt, max_tokens=1100)
    return {"text": text, "reviews": len(done), **meta}


def _rerank(sub) -> dict:
    from apps.review.suggest import suggest_reviewers
    cands = suggest_reviewers(sub)[:10]
    if not cands:
        raise ValueError("No reviewer candidates in the pool.")
    lines = []
    for i, c in enumerate(cands, 1):
        prof = c.get("profile")
        kws = ""
        if prof is not None:
            kws = ", ".join(i.name for i in prof.interests.all()[:8])
            if not kws:
                kws = (prof.expertise or "")[:120]
        coi = "; ".join(c.get("coi") or [])
        lines.append(f"{i}. {c['user'].full_name} — interests: {kws or '—'}; "
                     f"completed {c.get('completed', 0)}, open {c.get('pending', 0)}"
                     f"{'; possible COI: ' + coi if coi else ''}")
    prompt = (
        f"Submission:\n{_pub_meta(sub)}\n\nCandidate reviewers (pre-scored by "
        "keyword overlap and load):\n" + "\n".join(lines) +
        "\n\nPick the 5 best-fitting candidates. For each: their number, name, "
        "one line on topical fit. List candidates to avoid (COI or overload) "
        "separately. Judge only from the data above.")
    text, meta = _call(_system(sub.journal), prompt, max_tokens=800)
    return {"text": text, "candidates": len(cands), **meta}


_RUNNERS = {"desk_check": _desk_check, "metadata": _metadata,
            "synthesis": _synthesis, "rerank": _rerank}


def apply_metadata(sub, fields: set[str]) -> list[str]:
    report = get_report("metadata", sub.pk) or {}
    data = report.get("data") or {}
    pub = sub.current_publication
    if not pub or not data:
        return []
    from apps.publications.models import Keyword, PublicationTranslation
    loc = pub.primary_locale or sub.locale or "en"
    changed = []
    tr, _ = PublicationTranslation.objects.get_or_create(
        publication=pub, locale=loc)
    if "title" in fields and data.get("title"):
        tr.title = data["title"]
        changed.append("title")
    if "abstract" in fields and data.get("abstract"):
        tr.abstract = data["abstract"]
        changed.append("abstract")
    if changed:
        tr.save()
    if "keywords" in fields and data.get("keywords"):
        Keyword.objects.filter(publication=pub, locale=loc).delete()
        for i, term in enumerate(data["keywords"]):
            Keyword.objects.create(publication=pub, locale=loc, term=term, seq=i)
        changed.append("keywords")
    pub.__dict__.pop("_tr_cache", None)
    return changed
