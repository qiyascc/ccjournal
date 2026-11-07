import pytest

pytestmark = pytest.mark.django_db

HOST = "journal.ubermensch.cc"
ORCID_ID = "0000-0002-1825-0097"


def test_disabled_by_default():
    from apps.accounts.orcid_sso import is_configured
    assert is_configured() is False


def test_login_endpoint_400_when_disabled(client):
    r = client.get("/accounts/orcid/login/", HTTP_HOST=HOST)
    assert r.status_code == 400


def test_resolve_user_creates_then_reuses():
    from apps.accounts.orcid_sso import resolve_user

    user, created = resolve_user(ORCID_ID, "Ada Lovelace")
    assert created is True
    assert user.orcid == ORCID_ID
    assert user.given_name == "Ada" and user.family_name == "Lovelace"
    assert not user.has_usable_password()

    again, created2 = resolve_user(ORCID_ID, "Ada Lovelace")
    assert created2 is False and again.id == user.id


def test_login_redirects_to_orcid_when_configured(client, settings):
    settings.ORCID = {"client_id": "APP-XYZ", "client_secret": "sekret", "sandbox": True}
    r = client.get("/accounts/orcid/login/", HTTP_HOST=HOST)
    assert r.status_code == 302
    assert "sandbox.orcid.org/oauth/authorize" in r["Location"]
    assert "client_id=APP-XYZ" in r["Location"]


def test_callback_rejects_bad_state(client, settings):
    settings.ORCID = {"client_id": "APP-XYZ", "client_secret": "sekret", "sandbox": True}
    r = client.get("/accounts/orcid/callback/?code=abc&state=wrong", HTTP_HOST=HOST)
    assert r.status_code == 400
