import json

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(db, django_user_model):
    from django.contrib.auth.models import Group
    u = django_user_model.objects.create_user(
        email="ai-ed@example.org", password="pw-long-enough-123",
        given_name="Ed", is_staff=True)
    grp, _ = Group.objects.get_or_create(name="Editor")
    u.groups.add(grp)
    return u


@pytest.fixture
def ai_on(settings):
    from apps.plugins.models import PluginState
    from apps.plugins.registry import registry
    settings.AI_API_KEY = "test-key"
    PluginState.objects.update_or_create(
        plugin_key="ai_assistant", defaults={"enabled": True})
    registry.invalidate()
    yield
    PluginState.objects.filter(plugin_key="ai_assistant").update(enabled=False)
    registry.invalidate()


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def _fake(system, prompt, *, max_tokens=1200):
        calls.append({"system": system, "prompt": prompt})
        if "STRICT JSON" in prompt:
            return (json.dumps({"title": "AI Suggested Title",
                                "abstract": "AI abstract.",
                                "keywords": ["alpha", "beta"]}),
                    {"model": "test-model", "tokens_in": 10, "tokens_out": 5})
        return ("Section 1: fine.\nSection 2: none.",
                {"model": "test-model", "tokens_in": 10, "tokens_out": 5})

    from plugins.ai_assistant import service
    monkeypatch.setattr(service, "_call", _fake)
    return calls


def _drain():
    from apps.tasks.queue import run_due
    run_due(limit=10)


def test_disabled_leaves_no_trace(client, journal, make_pub, editor, settings):
    settings.AI_API_KEY = ""
    pub = make_pub(title="No AI Here")
    client.force_login(editor)
    html = client.get(f"/manage/integrity/{pub.submission_id}/").content.decode()
    assert "🤖" not in html
    resp = client.post(f"/manage/ai/run/desk_check/{pub.submission_id}/")
    assert resp.status_code == 404


def test_desk_check_flow(client, journal, make_pub, editor, ai_on, fake_llm):
    from plugins.ai_assistant import service
    pub = make_pub(title="Checkable Work")
    sub = pub.submission
    client.force_login(editor)
    resp = client.post(f"/manage/ai/run/desk_check/{sub.pk}/")
    assert resp.status_code == 302
    assert service.get_report("desk_check", sub.pk)["status"] == "pending"
    _drain()
    rep = service.get_report("desk_check", sub.pk)
    assert rep["status"] == "ok" and "Section 1" in rep["text"]
    html = client.get(f"/manage/integrity/{sub.pk}/").content.decode()
    assert "Desk-check summary" in html and "Section 1" in html


def test_metadata_extract_and_apply(client, journal, make_pub, editor,
                                    ai_on, fake_llm):
    from plugins.ai_assistant import service
    from apps.publications.models import PublicationTranslation
    pub = make_pub(title="Old Title")
    PublicationTranslation.objects.filter(publication=pub, locale="en").update(
        body="<p>" + "word " * 300 + "</p>")
    sub = pub.submission
    client.force_login(editor)
    client.post(f"/manage/ai/run/metadata/{sub.pk}/")
    _drain()
    rep = service.get_report("metadata", sub.pk)
    assert rep["status"] == "ok" and rep["data"]["title"] == "AI Suggested Title"
    client.post(f"/manage/ai/apply-metadata/{sub.pk}/",
                {"title": "on", "keywords": "on"})
    pub.refresh_from_db()
    pub.__dict__.pop("_tr_cache", None)
    assert pub.tr("en").title == "AI Suggested Title"
    terms = set(pub.keywords.values_list("term", flat=True))
    assert {"alpha", "beta"} <= terms


def test_synthesis_needs_reviews(client, journal, make_pub, editor,
                                 ai_on, fake_llm, django_user_model):
    from plugins.ai_assistant import service
    from apps.review.models import ReviewAssignment, ReviewRound
    from django.utils import timezone
    pub = make_pub(title="Reviewed Work")
    sub = pub.submission
    client.force_login(editor)
    client.post(f"/manage/ai/run/synthesis/{sub.pk}/")
    _drain()
    assert service.get_report("synthesis", sub.pk)["status"] == "error"
    rev = django_user_model.objects.create_user(
        email="ai-rev@example.org", password="pw-long-enough-123", given_name="R")
    rnd = ReviewRound.objects.create(submission=sub)
    ReviewAssignment.objects.create(
        review_round=rnd, reviewer=rev, recommendation=1,
        comments_for_author="Solid work.", date_completed=timezone.now())
    client.post(f"/manage/ai/run/synthesis/{sub.pk}/")
    _drain()
    rep = service.get_report("synthesis", sub.pk)
    assert rep["status"] == "ok" and rep["reviews"] == 1
    html = client.get(f"/manage/reviews/{sub.pk}/").content.decode()
    assert "Review synthesis" in html


def test_auto_desk_check_on_submit(journal, make_pub, ai_on, fake_llm):
    from apps.plugins.hooks import hooks
    from apps.tasks.models import Job
    from plugins.ai_assistant import service
    pub = make_pub(title="Fresh Submission")
    sub = pub.submission
    before = Job.objects.count()
    hooks.do_action("submission.submitted", submission=sub)
    assert Job.objects.count() == before + 1
    assert service.get_report("desk_check", sub.pk)["status"] == "pending"


def test_non_editor_cannot_run(client, journal, make_pub, user, ai_on):
    pub = make_pub(title="Locked")
    client.force_login(user)
    assert client.post(
        f"/manage/ai/run/desk_check/{pub.submission_id}/").status_code == 404
