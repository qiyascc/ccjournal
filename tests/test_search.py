from apps.search.services import fold


def test_fold_dotted_and_dotless_i():
    assert fold("İSTANBUL") == "istanbul"
    assert fold("ILIQ") == "iliq"


def test_fold_azerbaijani_schwa():
    assert fold("Əliyev") == "eliyev"


def test_fold_turkish_diacritics():
    assert fold("Çağrı") == "cagri"
    assert fold("ÖĞÜŞ") == "ogus"


def test_fold_empty_and_none():
    assert fold("") == ""
    assert fold(None) == ""
