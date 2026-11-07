import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser(django_user_model):
    return django_user_model.objects.create_superuser(
        email="pdf-admin@example.org", password="pw-long-enough-123", given_name="P")


def test_add_view_ships_default_design(client, journal, superuser):
    client.force_login(superuser)
    html = client.get("/admin/publications/pdftemplate/add/").content.decode()
    assert "epd-app" in html
    assert "data-default='{&quot;colors&quot;" in html


def test_change_view_has_designer_and_preview_url(client, journal, superuser):
    from apps.publications.models import PdfTemplate
    tpl = PdfTemplate.objects.create(journal=journal, name="D1")
    client.force_login(superuser)
    resp = client.get(f"/admin/publications/pdftemplate/{tpl.pk}/change/")
    html = resp.content.decode()
    assert "epd-app" in html and "vendor/Sortable" in html
    assert f"/admin/publications/pdftemplate/{tpl.pk}/preview/" in html
    assert "frame-src 'self' blob:" in resp.headers.get("Content-Security-Policy", "")


def test_preview_renders_pdf_with_unsaved_design(client, journal, make_pub,
                                                 issue_published, superuser):
    import json
    from apps.publications.models import DEFAULT_PDF_DESIGN, PdfTemplate
    from apps.publications.services import PublicationService
    pub = make_pub(issue=issue_published, title="Preview Article")
    PublicationService.publish(pub)
    tpl = PdfTemplate.objects.create(journal=journal, name="D2")
    client.force_login(superuser)
    design = json.loads(json.dumps(DEFAULT_PDF_DESIGN))
    design["colors"]["accent"] = "#ff0000"
    resp = client.post(f"/admin/publications/pdftemplate/{tpl.pk}/preview/",
                       {"mode": "visual", "design": json.dumps(design)})
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    tpl.refresh_from_db()
    assert not tpl.design  # önizleme kaydedilmemiş tasarımı DB'ye yazmaz


def test_preview_without_publication_says_so(client, journal, superuser):
    from apps.publications.models import PdfTemplate
    tpl = PdfTemplate.objects.create(journal=journal, name="D3")
    client.force_login(superuser)
    resp = client.post(f"/admin/publications/pdftemplate/{tpl.pk}/preview/", {})
    assert resp.status_code == 404
    assert b"No published article" in resp.content


def test_generate_pdf_galley_visual_mode(journal, make_pub, issue_published):
    from apps.publications.models import DEFAULT_PDF_DESIGN, PdfTemplate
    from apps.publications.pdf import generate_pdf_galley
    from apps.publications.services import PublicationService
    pub = make_pub(issue=issue_published, title="Galley Visual")
    PublicationService.publish(pub)
    PdfTemplate.objects.create(journal=journal, name="Active", mode="visual",
                               design=DEFAULT_PDF_DESIGN, is_active=True)
    g = generate_pdf_galley(pub)
    assert g.is_approved and g.file
    with g.file.file.open("rb") as fh:
        assert fh.read(4) == b"%PDF"
