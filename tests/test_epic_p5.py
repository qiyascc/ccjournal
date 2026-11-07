import io
import json
import zipfile

import pytest
from django.core import mail
from django.utils import timezone

pytestmark = pytest.mark.django_db

UA = "Mozilla/5.0 (pytest)"


@pytest.fixture
def editor(db, django_user_model):
    from django.contrib.auth.models import Group
    u = django_user_model.objects.create_user(
        email="p5-ed@example.org", password="pw-long-enough-123",
        given_name="Ed", is_staff=True)
    grp, _ = Group.objects.get_or_create(name="Editor")
    u.groups.add(grp)
    return u


@pytest.fixture
def published(journal, make_pub, issue_published):
    from apps.publications.services import PublicationService
    journal.enable_doi = True
    journal.doi_prefix = "10.5555"
    journal.save(update_fields=["enable_doi", "doi_prefix"])
    pub = make_pub(issue=issue_published, title="P5 Flagship Article")
    PublicationService.publish(pub)
    return pub



def test_cascade_package_and_import(client, journal, make_pub, editor):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.review.models import EditorialDecision
    from apps.review.services import WorkflowService
    from apps.submissions.models import SubmissionFile, FileStage
    from apps.submissions.package import import_package

    pub = make_pub(title="Declined Work")
    sub = pub.submission
    SubmissionFile.objects.create(
        submission=sub, file=SimpleUploadedFile("ms.pdf", b"%PDF-1.4"),
        original_filename="ms.pdf", file_size=8, file_stage=FileStage.SUBMISSION)
    url = f"/work/{sub.author_token}/package.zip"
    assert client.get(url).status_code == 404
    WorkflowService.record_decision(sub, editor,
                                    EditorialDecision.Decision.DECLINE,
                                    notify_author=False)
    resp = client.get(url)
    assert resp.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    meta = json.loads(z.read("package.json"))
    assert meta["translations"][0]["title"] == "Declined Work"
    assert any(n.startswith("files/") for n in z.namelist())
    new_sub, info = import_package(io.BytesIO(resp.content), journal)
    assert info["files"] == 1
    assert new_sub.current_publication.tr("en").title == "Declined Work"


def test_coauthor_notice_and_credit_approval(client, journal, section, user,
                                             django_user_model):
    from apps.publications.models import Author, Publication, PublicationTranslation
    from apps.submissions.models import Submission
    from apps.comms.services import submission_created
    sub = Submission.objects.create(journal=journal, submitter=user, locale="en")
    pub = Publication.objects.create(submission=sub, primary_locale="en",
                                     section=section)
    PublicationTranslation.objects.create(publication=pub, locale="en",
                                          title="Multi Author Work")
    sub.current_publication = pub
    sub.save(update_fields=["current_publication"])
    Author.objects.create(publication=pub, given_name=user.given_name,
                          email=user.email, seq=0)
    co = Author.objects.create(publication=pub, given_name="Co", family_name="A",
                               email="coauthor@example.org", seq=1,
                               credit_roles=["software"])
    mail.outbox.clear()
    submission_created.send(sender=Submission, submission=sub)
    co_mail = next(m for m in mail.outbox if "coauthor@example.org" in m.to)
    assert f"/work/{sub.author_token}/credit/{co.access_token}/" in co_mail.body
    page = client.get(f"/work/{sub.author_token}/credit/{co.access_token}/")
    assert b"Software" in page.content
    client.post(f"/work/{sub.author_token}/credit/{co.access_token}/")
    co.refresh_from_db()
    assert co.credit_approved_at is not None


def test_issue_checklist_action(client, journal, editor, make_pub, issue_unpublished):
    make_pub(issue=issue_unpublished, approved_galley=False)
    client.force_login(editor)
    resp = client.post("/admin/journals/issue/", {
        "action": "action_issue_checklist",
        "_selected_action": [issue_unpublished.pk]})
    html = resp.content.decode()
    assert "Pre-publish checklist" in html
    assert "galley" in html.lower()


def test_undo_send_decision_email(journal, make_pub, editor):
    from constance.test import override_config
    from apps.review.models import EditorialDecision
    from apps.review.services import WorkflowService
    from apps.tasks.models import Job
    from apps.tasks.queue import run_due
    pub = make_pub(title="Undo Paper")
    mail.outbox.clear()
    with override_config(EMAIL_UNDO_MINUTES=5):
        WorkflowService.record_decision(pub.submission, editor,
                                        EditorialDecision.Decision.ACCEPT)
    assert len(mail.outbox) == 0
    job = Job.objects.filter(func__endswith="send_decision_email").latest("id")
    assert job.run_after > timezone.now()
    Job.objects.filter(pk=job.pk).update(run_after=timezone.now())
    run_due()
    assert len(mail.outbox) == 1
    assert "accepted" in mail.outbox[0].body.lower()


def test_reviewer_self_service_profile_and_pool(client, journal, user):
    from datetime import timedelta
    from apps.review.services import ReviewerService
    prof = ReviewerService.ensure_profile(user)
    client.force_login(user)
    future = (timezone.localdate() + timedelta(days=30)).isoformat()
    client.post("/accounts/profile/", {
        "given_name": user.given_name, "family_name": "", "affiliation": "",
        "affiliation_ror": "", "orcid": "", "country": "", "biography": "",
        "preferred_locale": "en", "unavailable_until": future,
        "max_per_year": "3", "public_listing": "on"})
    prof.refresh_from_db()
    assert prof.public_listing and str(prof.unavailable_until) == future
    assert prof.max_per_year == 3
    assert prof not in ReviewerService.pool(available_only=True)


def test_smart_reviewer_suggestions_and_coi(journal, make_pub, django_user_model):
    from apps.review.models import ReviewInterest
    from apps.review.services import ReviewerService
    from apps.review.suggest import suggest_reviewers
    pub = make_pub(title="Quantum Computing Advances")
    good = django_user_model.objects.create_user(
        email="expert@example.org", password="pw-long-enough-123", given_name="Ex",
        affiliation="Other Uni")
    gp = ReviewerService.ensure_profile(good)
    interest = ReviewInterest.objects.create(name="quantum computing")
    gp.interests.add(interest)
    coi_user = django_user_model.objects.create_user(
        email="samelab@example.org", password="pw-long-enough-123", given_name="Coi")
    cp = ReviewerService.ensure_profile(coi_user)
    cp.affiliation = "Test University"
    cp.save()
    author = pub.authors.first()
    author.affiliation = "Test University"
    author.save(update_fields=["affiliation"])
    cp.interests.add(interest)
    out = suggest_reviewers(pub.submission)
    emails = [r["user"].email for r in out]
    assert "expert@example.org" in emails
    coi_row = next(r for r in out if r["user"].email == "samelab@example.org")
    assert coi_row["coi"]


def test_accessibility_page_and_listen_button(client, journal, published):
    assert b"Accessibility statement" in client.get("/accessibility/").content
    html = client.get(f"/article/{published.submission_id}/",
                      HTTP_USER_AGENT=UA).content.decode()
    assert 'id="cc-listen"' in html


def test_statements_license_saved_and_shown(client, journal, make_pub,
                                            issue_published, user):
    from apps.publications.services import PublicationService
    pub = make_pub(title="Stated Work")
    sub = pub.submission
    client.force_login(user)
    client.post(f"/submit/{sub.pk}/confirm/", {
        "data_availability": "Data at https://doi.org/10.5281/zenodo.1",
        "ai_statement": "No AI tools were used.",
        "license": "https://creativecommons.org/licenses/by-nc/4.0/"})
    pub.refresh_from_db()
    assert "zenodo" in pub.data_availability
    assert pub.license_url.endswith("by-nc/4.0/")
    pub.issue = issue_published
    pub.save(update_fields=["issue"])
    PublicationService.publish(pub)
    html = client.get(f"/article/{sub.pk}/", HTTP_USER_AGENT=UA).content.decode()
    assert "Data availability" in html and "CC BY-NC" in html
    assert "No AI tools" in html


def test_hreflang_and_og_image(client, journal, published):
    from apps.publications.models import PublicationTranslation
    PublicationTranslation.objects.create(
        publication=published, locale="az", title="AZ başlıq")
    html = client.get(f"/article/{published.submission_id}/",
                      HTTP_USER_AGENT=UA).content.decode()
    assert 'hreflang="az"' in html and 'hreflang="en"' in html
    assert f"/article/{published.submission_id}/card.png" in html


def test_og_card_png(client, journal, published):
    resp = client.get(f"/article/{published.submission_id}/card.png")
    assert resp.status_code == 200
    body = b"".join(resp.streaming_content) if resp.streaming else resp.content
    assert body[:8] == b"\x89PNG\r\n\x1a\n"


def test_scholar_citation_meta(client, journal, published):
    import re
    html = client.get(f"/article/{published.submission_id}/",
                      HTTP_USER_AGENT=UA).content.decode()
    for tag in ("citation_title", "citation_author", "citation_pdf_url",
                "citation_journal_title", "citation_publication_date",
                "citation_language"):
        assert f'name="{tag}"' in html, tag
    assert '<meta name="citation_volume" content="1">' in html
    assert '<meta name="citation_issue" content="1">' in html
    m = re.search(r'citation_pdf_url" content="([^"]+)"', html)
    assert m and f"/article/{published.submission_id}/galley/" in m.group(1)


def test_most_cited_page(client, journal, published):
    published.cited_by_count = 9
    published.save(update_fields=["cited_by_count"])
    html = client.get("/most-cited/").content.decode()
    assert "P5 Flagship Article" in html and "9" in html


def test_issue_toc_in_reader_email(journal, published, issue_published,
                                   django_user_model):
    from apps.comms.models import EmailTemplate
    from apps.comms.tasks import notify_readers_new_issue
    for t in EmailTemplate.objects.filter(key="issue_published"):
        if "{{ toc }}" not in t.body:
            t.body = t.body.replace("Read it here", "{{ toc }}\n\nRead it here")
            t.save(update_fields=["body"])
    django_user_model.objects.create_user(
        email="toc-reader@example.org", password="pw-long-enough-123",
        given_name="R", notify_new_issue=True)
    mail.outbox.clear()
    notify_readers_new_issue(issue_published.pk)
    body = mail.outbox[0].body
    assert "P5 Flagship Article" in body


def test_sparkline_on_article(client, journal, published):
    from apps.stats.models import Metric, MetricDay
    MetricDay.objects.create(submission=published.submission,
                             metric=Metric.ABSTRACT_VIEW,
                             date=timezone.localdate(), count=5)
    html = client.get(f"/article/{published.submission_id}/",
                      HTTP_USER_AGENT=UA).content.decode()
    assert "Readership, last 12 months" in html and "<polyline" in html


def test_restore_drill(tmp_path, settings):
    import sqlite3
    from django.core.management import call_command
    backups = tmp_path / "backups"
    backups.mkdir()
    db = backups / "db-2026-01-01.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE journals_journal (id int)")
    con.execute("INSERT INTO journals_journal VALUES (1)")
    con.commit(); con.close()
    settings.BASE_DIR = tmp_path
    out = io.StringIO()
    call_command("restore_drill", stdout=out)
    text = out.getvalue()
    assert "integrity_check: ok" in text and "passed" in text



def test_related_articles(client, journal, make_pub, issue_published):
    from apps.publications.services import PublicationService
    a = make_pub(issue=issue_published, title="Deep Neural Networks Study")
    b = make_pub(issue=issue_published, title="Neural Networks Deep Analysis")
    PublicationService.publish(a)
    PublicationService.publish(b)
    html = client.get(f"/article/{a.submission_id}/",
                      HTTP_USER_AGENT=UA).content.decode()
    assert "You may also like" in html and "Neural Networks Deep Analysis" in html


def test_search_facets(client, journal, published):
    resp = client.get("/search/", {"q": "Flagship"})
    html = resp.content.decode()
    assert "All years" in html
    year = published.date_published.year
    filtered = client.get("/search/", {"q": "Flagship", "year": year}).content.decode()
    assert "P5 Flagship Article" in filtered
    none = client.get("/search/", {"q": "Flagship", "year": year - 5}).content.decode()
    assert "P5 Flagship Article" not in none


def test_keyword_and_author_pages(client, journal, published):
    html = client.get("/keyword/computing/").content.decode()
    assert "P5 Flagship Article" in html
    author = published.authors.first()
    ahtml = client.get(f"/author/{author.pk}/").content.decode()
    assert "Ada Lovelace" in ahtml and "P5 Flagship Article" in ahtml


def test_section_and_keyword_feeds(client, journal, published, section):
    r1 = client.get(f"/feed/section/{section.pk}/")
    assert r1.status_code == 200 and b"P5 Flagship Article" in r1.content
    r2 = client.get("/feed/keyword/computing/")
    assert r2.status_code == 200 and b"P5 Flagship Article" in r2.content



def test_editorial_ics(client, journal, make_pub, editor, django_user_model):
    from apps.review.ics import calendar_token
    from apps.review.models import ReviewRound
    from apps.review.services import ReviewService
    pub = make_pub()
    rnd = ReviewRound.objects.create(submission=pub.submission)
    rev = django_user_model.objects.create_user(
        email="ics-rev@example.org", password="pw-long-enough-123", given_name="I")
    ReviewService.assign_reviewer(rnd, rev, due=timezone.localdate())
    token = calendar_token(editor)
    resp = client.get(f"/manage/calendar/{token}/editorial.ics")
    assert resp.status_code == 200
    assert b"BEGIN:VCALENDAR" in resp.content and b"Review due" in resp.content
    assert client.get("/manage/calendar/garbage/editorial.ics").status_code == 404


def test_dossier_pdf(client, journal, make_pub, editor):
    from apps.review.models import EditorialDecision
    from apps.review.services import WorkflowService
    pub = make_pub(title="Dossier Paper")
    WorkflowService.record_decision(pub.submission, editor,
                                    EditorialDecision.Decision.SEND_TO_REVIEW,
                                    notify_author=False)
    client.force_login(editor)
    resp = client.get(f"/manage/dossier/{pub.submission_id}.pdf")
    assert resp.status_code == 200 and resp.content[:4] == b"%PDF"


def test_email_template_test_send(client, journal, editor, django_user_model):
    su = django_user_model.objects.create_superuser(
        email="su-p5@example.org", password="pw-long-enough-123", given_name="S")
    client.force_login(su)
    from apps.comms.models import EmailTemplate
    tpl = EmailTemplate.objects.filter(key="decision_accept", locale="en",
                                       journal=None).first()
    mail.outbox.clear()
    client.post("/admin/comms/emailtemplate/", {
        "action": "action_send_test", "_selected_action": [tpl.pk]})
    assert any(m.subject.startswith("[TEST]") for m in mail.outbox)


def test_appeal_flow(client, journal, make_pub, editor):
    from apps.review.models import Appeal, EditorialDecision
    from apps.review.services import WorkflowService
    pub = make_pub(title="Appealed Paper")
    sub = pub.submission
    WorkflowService.record_decision(sub, editor,
                                    EditorialDecision.Decision.DECLINE,
                                    notify_author=False)
    reason = "The second reviewer misread our methodology section entirely, and " \
             "the decision ignored the positive first report."
    resp = client.post(f"/work/{sub.author_token}/appeal/", {"reason": reason})
    assert resp.status_code == 302
    appeal = Appeal.objects.get(submission=sub)
    assert appeal.status == Appeal.Status.OPEN
    assert editor.notifications.filter(type="appeal_filed").exists()
    client.post(f"/work/{sub.author_token}/appeal/", {"reason": reason})
    assert Appeal.objects.filter(submission=sub).count() == 1
    html = client.get(f"/work/{sub.author_token}/").content.decode()
    assert "Appeal status" in html


def test_retroactive_doi_action(client, journal, editor, make_pub, issue_published):
    from apps.publications.services import PublicationService
    pub = make_pub(issue=issue_published, title="Old Article")
    PublicationService.publish(pub)
    assert pub.doi_id is None
    journal.enable_doi = True
    journal.doi_prefix = "10.7777"
    journal.save(update_fields=["enable_doi", "doi_prefix"])
    client.force_login(editor)
    client.post("/admin/publications/publication/", {
        "action": "action_mint_retroactive", "_selected_action": [pub.pk]})
    pub.refresh_from_db()
    assert pub.doi_id and pub.doi.doi.startswith("10.7777/")


def test_theme_editor(client, journal, django_user_model):
    su = django_user_model.objects.create_superuser(
        email="theme-su@example.org", password="pw-long-enough-123", given_name="T")
    client.force_login(su)
    assert client.get("/manage/theme/").status_code == 200
    client.post("/manage/theme/", {"accent": "#ff0000"})
    journal.refresh_from_db()
    assert journal.settings["theme_vars"]["accent"] == "#ff0000"
    css = client.get("/theme.css").content.decode()
    assert "--accent:#ff0000" in css
    client.post("/manage/theme/", {"action": "reset"})
    journal.refresh_from_db()
    assert "theme_vars" not in journal.settings



def test_ror_and_funder_proxies(client, journal, user, monkeypatch):
    import apps.api.metadata_proxy as mp
    assert client.get("/api/suggest/ror?q=test").status_code == 302
    client.force_login(user)
    monkeypatch.setattr(mp, "_fetch_json", lambda url: {
        "items": [{"id": "https://ror.org/05abc", "names": [
            {"value": "Test University", "types": ["ror_display"]}],
            "locations": [{"geonames_details": {"country_name": "Azerbaijan"}}]}]}
        if "ror.org" in url else
        {"message": {"items": [{"name": "Science Fund", "id": "501100001"}]}})
    r = client.get("/api/suggest/ror?q=test uni").json()
    assert r["results"][0]["ror"] == "https://ror.org/05abc"
    f = client.get("/api/suggest/funder?q=science").json()
    assert f["results"][0]["id"] == "10.13039/501100001"


def test_newsletter_double_opt_in_and_issue_mail(client, journal, published,
                                                 issue_published):
    from apps.comms.models import NewsletterSubscriber
    from apps.comms.tasks import notify_readers_new_issue
    mail.outbox.clear()
    client.post("/newsletter/", {"email": "reader@example.org"})
    sub = NewsletterSubscriber.objects.get(email="reader@example.org")
    assert sub.confirmed_at is None
    body = mail.outbox[-1].body
    token = body.split("/newsletter/confirm/")[1].split("/")[0]
    client.get(f"/newsletter/confirm/{token}/")
    sub.refresh_from_db()
    assert sub.confirmed_at is not None
    mail.outbox.clear()
    notify_readers_new_issue(issue_published.pk)
    assert any("reader@example.org" in m.to for m in mail.outbox)
    unsub = next(m for m in mail.outbox if "reader@example.org" in m.to)
    utoken = unsub.body.split("/newsletter/unsubscribe/")[1].split("/")[0]
    client.get(f"/newsletter/unsubscribe/{utoken}/")
    assert not NewsletterSubscriber.objects.filter(
        email="reader@example.org").exists()


def test_cfp_module(client, journal):
    from apps.journals.models import CallForPapers
    CallForPapers.objects.create(journal=journal, title="Special Issue on AI Ethics",
                                 deadline=timezone.localdate(), is_active=True)
    assert "Special Issue on AI Ethics" in client.get("/calls/").content.decode()
    assert "Special Issue on AI Ethics" in client.get("/").content.decode()


def test_ai_bot_robots_policy(client, journal):
    from constance.test import override_config
    base = client.get("/robots.txt").content.decode()
    assert "GPTBot" not in base
    with override_config(BLOCK_AI_BOTS=True):
        blocked = client.get("/robots.txt").content.decode()
    assert "User-agent: GPTBot" in blocked and "Disallow: /" in blocked
    assert blocked.rstrip().endswith("sitemap.xml")
