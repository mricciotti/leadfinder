import pytest

import contacts


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+55 11 3815-2600", ("1138152600", "fixo")),
        ("+55 (11) 98888-7777", ("11988887777", "celular")),
        ("11 98888-7777", ("11988887777", "celular")),
        ("(011) 3815-2600", ("1138152600", "fixo")),
        ("011 98888-7777", ("11988887777", "celular")),
        ("0800 123 4567", ("08001234567", "outro")),
        ("3815-2600", (None, "invalido")),
        ("+55 10 3815-2600", (None, "invalido")),
        ("11 8888-777", (None, "invalido")),
        ("11 18888-7777", (None, "invalido")),
        ("ramal", (None, None)),
        (None, (None, None)),
    ],
)
def test_normalize_phone(raw, expected):
    assert contacts.normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "value, expected",
    [("SP", "SP"), (" rj ", "RJ"), ("BR-MG", "MG"), ("São Paulo", None), (None, None)],
)
def test_normalize_uf(value, expected):
    assert contacts.normalize_uf(value) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://cantina.com.br", "https://cantina.com.br"),
        ("www.Cantina.com.br/menu", "https://www.cantina.com.br/menu"),
        ("HTTP://cantina.com.br", "http://cantina.com.br"),
        (
            "https://cantina.com.br/?utm_source=osm&utm_medium=x&page=2",
            "https://cantina.com.br/?page=2",
        ),
        (
            "https://cantina.com.br/?gclid=1&fbclid=2&msclkid=3&mc_cid=4&mc_eid=5&id=7",
            "https://cantina.com.br/?id=7",
        ),
        ("https://cantina.com.br/loja?q=a%20b&x=", "https://cantina.com.br/loja?q=a%20b&x="),
        ("https://cantina.com.br:8080/a", "https://cantina.com.br:8080/a"),
        ("cantina", None),
        ("ftp://cantina.com.br", None),
        ("https://user:senha@cantina.com.br", None),
        ("https://cantina.com.br:porta", None),
        ("Rua A, 10", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_url(raw, expected):
    assert contacts.normalize_url(raw) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://instagram.com/cantina", "instagram"),
        ("https://www.instagram.com/cantina", "instagram"),
        ("https://m.facebook.com/cantina", "facebook"),
        ("https://fb.me/cantina", "facebook"),
        ("https://instagr.am/cantina", "instagram"),
        ("https://lnkd.in/cantina", "linkedin"),
        ("https://linktr.ee/cantina", "pagina_de_links"),
        ("https://www.ifood.com.br/delivery/sao-paulo-sp/cantina", "delivery"),
        ("https://wa.me/5511988887777", "whatsapp"),
        ("https://api.whatsapp.com/send?phone=5511988887777", "whatsapp"),
        ("https://cantina.com.br", "propria"),
        ("https://notinstagram.com/cantina", "propria"),
        ("https://instagram.com.golpe.com/cantina", "propria"),
    ],
)
def test_classify_url(url, expected):
    assert contacts.classify_url(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://cantina.wixsite.com/site", True),
        ("https://sites.google.com/view/cantina", True),
        ("https://cantina.blogspot.com", True),
        ("https://cantina.com.br", False),
        ("https://wixsitecantina.com.br", False),
    ],
)
def test_is_free_site(url, expected):
    assert contacts.is_free_site(url) is expected


@pytest.mark.parametrize(
    "email, expected",
    [
        ("contato@cantina.com.br", "proprio"),
        ("cantina@gmail.com", "generico"),
        ("Cantina@Hotmail.com", "generico"),
        ("semarroba", None),
        (None, None),
    ],
)
def test_email_kind(email, expected):
    assert contacts.email_kind(email) == expected


@pytest.mark.parametrize(
    "national, expected",
    [
        ("1138152600", "(11) 3815-2600"),
        ("11988887777", "(11) 98888-7777"),
        ("08001234567", "0800 123 4567"),
        (None, None),
    ],
)
def test_format_phone(national, expected):
    assert contacts.format_phone(national) == expected


def test_whatsapp_url_uses_the_country_code():
    assert contacts.whatsapp_url("11988887777") == "https://wa.me/5511988887777"


@pytest.mark.parametrize(
    "text, expected",
    [("Saúde", "saude"), ("  Vila   Mariana ", "vila mariana"), ("São-Paulo!", "sao paulo"), (None, "")],
)
def test_text_key(text, expected):
    assert contacts.text_key(text) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("cantina.boa", "cantina.boa"),
        ("@cantina_boa", "cantina_boa"),
        ("https://www.instagram.com/cantina/", "https://www.instagram.com/cantina/"),
        ("instagram.com/cantina", "https://instagram.com/cantina"),
        ("https://facebook.com/cantina", None),
        ("não é handle", None),
        ("", None),
    ],
)
def test_normalize_instagram(raw, expected):
    assert contacts.normalize_instagram(raw) == expected
