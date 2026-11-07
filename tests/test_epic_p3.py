
import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(db, django_user_model):
    from django.contrib.auth.models import Group
    u = django_user_model.objects.create_user(
        email="p3-ed@example.org", password="pw-long-enough-123",
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
    pub = make_pub(issue=issue_published, title="P3 Article")
    PublicationService.publish(pub)   # DOI mint edilir
    return pub


# --- Karar e-postasına hakem yorumları -----------------------------------------

def test_decide_preview_appends_reviewer_comments(client, journal, make_pub, editor,
                                                  django_user_model):
    from django.utils import timezone
    from apps.review.models import EditorialDecision, ReviewRound
    from apps.review.services import ReviewService
    pub = make_pub(title="With Reviews")
    sub = pub.submission
    reviewer = django_user_model.objects.create_user(
        email="p3-rev@example.org", password="pw-long-enough-123", given_name="R")
    rnd = ReviewRound.objects.create(submission=sub)
    a = ReviewService.assign_reviewer(rnd, reviewer)
    a.comments_for_author = "Please expand the methods section."
    a.recommendation = 2
    a.date_completed = timezone.now()
    a.save()
    client.force_login(editor)
    resp = client.post("/admin/submissions/submission/", {
        "action": "action_decide_with_email", "_selected_action": [sub.pk],
        "preview": "1", "decision": EditorialDecision.Decision.PENDING_REVISIONS,
        "note": "See reviews.", "include_reviews": "on"})
    html = resp.content.decode()
    assert "Reviewer 1" in html and "expand the methods" in html


# --- Hakem karşılaştırma sayfası --------------------------------------------------

def test_reviews_compare_page(client, journal, make_pub, editor, django_user_model):
    from django.utils import timezone
    from apps.review.models import ReviewRound
    from apps.review.services import ReviewService
    pub = make_pub(title="Compare Me")
    sub = pub.submission
    reviewer = django_user_model.objects.create_user(
        email="p3-rev2@example.org", password="pw-long-enough-123", given_name="R2")
    rnd = ReviewRound.objects.create(submission=sub)
    a = ReviewService.assign_reviewer(rnd, reviewer)
    a.comments_for_editor = "Confidential: borderline."
    a.form_responses = [{"item": 1, "label": "Quality?", "value": ["High", "Novel"]}]
    a.date_completed = timezone.now()
    a.save()
    client.force_login(editor)
    html = client.get(f"/manage/reviews/{sub.pk}/").content.decode()
    assert "Compare Me" in html
    assert "Confidential: borderline." in html
    assert "High, Novel" in html            # liste değeri virgüllü metne normalize
    client.logout()
    assert client.get(f"/manage/reviews/{sub.pk}/").status_code == 302


# --- JATS galley + endpoint ---------------------------------------------------------

def test_jats_endpoint_and_galley(client, journal, published):
    resp = client.get(f"/article/{published.submission_id}/jats.xml")
    assert resp.status_code == 200
    assert b"<article" in resp.content and b"journal-meta" in resp.content
    from apps.publications.jats import generate_jats_galley
    g = generate_jats_galley(published)
    assert g.label == "XML" and g.is_approved
    with g.file.file.open("rb") as fh:
        assert b"article-title" in fh.read()


# --- Crossmark ------------------------------------------------------------------------

def test_crossmark_in_deposit_when_policy_set(journal, published, monkeypatch):
    from django.utils import timezone
    from lxml import etree
    import apps.metadata.serializers as ser
    published.retracted_at = timezone.localdate()
    published.save(update_fields=["retracted_at"])
    xml_off = etree.tostring(ser.to_crossref_deposit([published])).decode()
    assert "crossmark" not in xml_off                      # politika yok → blok yok
    monkeypatch.setattr(ser, "_crossmark_policy", lambda: "10.5555/policy")
    xml_on = etree.tostring(ser.to_crossref_deposit([published])).decode()
    assert "crossmark_policy" in xml_on and "10.5555/policy" in xml_on
    assert 'type="retraction"' in xml_on


# --- COUNTER + PubMed -------------------------------------------------------------------

def test_counter_csv(client, journal, published, editor):
    from django.utils import timezone
    from apps.stats.models import Metric, MetricDay
    MetricDay.objects.create(submission=published.submission,
                             metric=Metric.GALLEY_VIEW,
                             date=timezone.localdate(), count=4)
    client.force_login(editor)
    body = client.get("/reports/counter.csv").content.decode()
    assert "TR_J1" in body and "Total_Item_Requests" in body and ",4" in body
    assert "unaudited" in body.lower() or "not COUNTER audited" in body


def test_pubmed_export(client, journal, published, editor):
    assert client.get("/export/pubmed").status_code == 403
    client.force_login(editor)
    resp = client.get("/export/pubmed")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "<ArticleSet>" in body and "P3 Article" in body
    assert "<LastName>Lovelace</LastName>" in body


# --- OpenCitations cited-by ---------------------------------------------------------------

def test_fetch_cited_by_updates_and_shows(client, journal, published, monkeypatch):
    import apps.publications.tasks as ptasks
    monkeypatch.setattr(ptasks, "_fetch_count", lambda doi: 17)
    out = ptasks.fetch_cited_by()
    assert out["updated"] == 1 and out["errors"] == 0
    published.refresh_from_db()
    assert published.cited_by_count == 17
    html = client.get(f"/article/{published.submission_id}/",
                      HTTP_USER_AGENT="Mozilla/5.0 t").content.decode()
    assert "Cited by 17" in html
    # taze kayıt tekrar çekilmez
    assert ptasks.fetch_cited_by()["updated"] == 0


# --- ORCID push ------------------------------------------------------------------------------

def test_orcid_push_gated_and_posts(journal, published, django_user_model,
                                    monkeypatch, settings):
    from apps.accounts import orcid_push
    assert orcid_push.push_publication(published.pk)["reason"] == "orcid push disabled"

    settings.ORCID = {"client_id": "x", "client_secret": "y",
                      "sandbox": True, "push": True}
    author = published.authors.first()
    author.orcid = "0000-0002-1825-0097"
    author.save(update_fields=["orcid"])
    django_user_model.objects.create_user(
        email="orcid-owner@example.org", password="pw-long-enough-123",
        given_name="O", orcid="0000-0002-1825-0097",
        orcid_access_token="tok123", orcid_token_scope="/authenticate /activities/update")

    calls = {}

    def fake_post(orcid, token, payload):
        calls["orcid"], calls["token"], calls["payload"] = orcid, token, payload
        return True, "HTTP 201"

    monkeypatch.setattr(orcid_push, "_post_work", fake_post)
    out = orcid_push.push_publication(published.pk)
    assert out == {"pushed": 1, "failed": 0, "skipped": 0}
    assert calls["orcid"] == "0000-0002-1825-0097" and calls["token"] == "tok123"
    assert calls["payload"]["title"]["title"]["value"] == "P3 Article"
    assert calls["payload"]["external-ids"]["external-id"][0]["external-id-type"] == "doi"


def test_orcid_push_skips_users_without_scope(journal, published, django_user_model,
                                              settings, monkeypatch):
    from apps.accounts import orcid_push
    settings.ORCID = {"client_id": "x", "client_secret": "y", "push": True}
    author = published.authors.first()
    author.orcid = "0000-0002-1825-0097"
    author.save(update_fields=["orcid"])
    django_user_model.objects.create_user(
        email="noscope@example.org", password="pw-long-enough-123",
        given_name="N", orcid="0000-0002-1825-0097",
        orcid_access_token="tok", orcid_token_scope="/authenticate")
    monkeypatch.setattr(orcid_push, "_post_work",
                        lambda *a: (_ for _ in ()).throw(AssertionError("must not post")))
    out = orcid_push.push_publication(published.pk)
    assert out == {"pushed": 0, "failed": 0, "skipped": 1}


# --- OJS importer ------------------------------------------------------------------------------

OJS_XML = """<?xml version="1.0"?>
<issues xmlns="http://pkp.sfu.ca">
 <issue>
  <issue_identification>
    <volume>7</volume><number>2</number><year>2019</year>
    <title locale="en_US">Autumn Issue</title>
  </issue_identification>
  <date_published>2019-10-01</date_published>
  <sections>
    <section ref="ART"><abbrev>ART</abbrev><title locale="en_US">Research Articles</title></section>
  </sections>
  <articles>
    <article locale="en_US" date_published="2019-10-01" section_ref="ART" stage="production">
      <id type="doi">10.9999/ojs-import-1</id>
      <title locale="en_US">Imported From OJS</title>
      <abstract locale="en_US">An abstract migrated from OJS.</abstract>
      <keywords locale="en_US"><keyword>migration</keyword><keyword>ojs</keyword></keywords>
      <authors>
        <author primary_contact="true">
          <givenname locale="en_US">Grace</givenname>
          <familyname locale="en_US">Hopper</familyname>
          <email>grace@navy.mil</email>
          <orcid>https://orcid.org/0000-0001-9999-0000</orcid>
          <affiliation locale="en_US">US Navy</affiliation>
        </author>
      </authors>
      <pages>10-24</pages>
      <submission_file id="55">
        <name locale="en_US">imported.pdf</name>
        <file filename="imported.pdf"><embed encoding="base64">JVBERi0xLjQgZmFrZQ==</embed></file>
      </submission_file>
      <article_galley>
        <name locale="en_US">PDF</name>
        <submission_file_ref id="55"/>
      </article_galley>
    </article>
  </articles>
 </issue>
</issues>
"""


def test_import_ojs_full_flow(tmp_path, journal, capsys):
    from django.core.management import call_command
    from apps.journals.models import Issue
    from apps.publications.models import Publication
    xml = tmp_path / "export.xml"
    xml.write_text(OJS_XML)
    call_command("import_ojs", str(xml))
    issue = Issue.objects.get(journal=journal, volume=7, number="2")
    assert issue.is_published
    pub = Publication.objects.get(doi__doi="10.9999/ojs-import-1")
    assert pub.issue_id == issue.pk
    assert pub.tr("en").title == "Imported From OJS"
    assert pub.pages == "10-24"
    assert pub.authors.get().family_name == "Hopper"
    assert pub.authors.get().orcid == "0000-0001-9999-0000"
    assert set(pub.keywords.values_list("term", flat=True)) == {"migration", "ojs"}
    assert pub.section.tr_value("title") == "Research Articles"
    g = pub.galleys.get()
    assert g.label == "PDF" and g.is_approved
    with g.file.file.open("rb") as fh:
        assert fh.read().startswith(b"%PDF-1.4")
    # idempotent: ikinci koşu atlar
    call_command("import_ojs", str(xml))
    assert Publication.objects.filter(doi__doi="10.9999/ojs-import-1").count() == 1


def test_import_ojs_dry_run_writes_nothing(tmp_path, journal):
    from django.core.management import call_command
    from apps.publications.models import Publication
    xml = tmp_path / "export.xml"
    xml.write_text(OJS_XML.replace("10.9999/ojs-import-1", "10.9999/dry-run-doi"))
    call_command("import_ojs", str(xml), "--dry-run")
    assert not Publication.objects.filter(doi__doi="10.9999/dry-run-doi").exists()
