import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

VALID_DDDS = {
    *range(11, 20),
    21, 22, 24, 27, 28,
    31, 32, 33, 34, 35, 37, 38,
    41, 42, 43, 44, 45, 46, 47, 48, 49,
    51, 53, 54, 55,
    *range(61, 70),
    71, 73, 74, 75, 77, 79,
    *range(81, 90),
    *range(91, 100),
}
NON_GEOGRAPHIC_PREFIXES = ("0800", "0300", "0500", "0900")
INSTAGRAM_HANDLE = re.compile(r"@?([A-Za-z0-9_.]{1,30})")

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

TRACKING_PARAMS = ("utm_", "gclid", "fbclid", "msclkid", "mc_cid", "mc_eid")

URL_KINDS = {
    "instagram.com": "instagram",
    "instagr.am": "instagram",
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "fb.me": "facebook",
    "linkedin.com": "linkedin",
    "lnkd.in": "linkedin",
    "x.com": "x",
    "twitter.com": "x",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "linktr.ee": "pagina_de_links",
    "beacons.ai": "pagina_de_links",
    "bio.link": "pagina_de_links",
    "taplink.cc": "pagina_de_links",
    "ifood.com.br": "delivery",
    "rappi.com.br": "delivery",
    "aiqfome.com": "delivery",
    "anota.ai": "delivery",
    "wa.me": "whatsapp",
    "whatsapp.com": "whatsapp",
}

FREE_SITE_HOSTS = (
    "wixsite.com",
    "sites.google.com",
    "blogspot.com",
    "wordpress.com",
    "weebly.com",
    "godaddysites.com",
    "business.site",
    "webnode.page",
)

GENERIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.com.br", "outlook.com",
    "outlook.com.br", "live.com", "msn.com", "yahoo.com", "yahoo.com.br", "icloud.com",
    "uol.com.br", "bol.com.br", "terra.com.br", "ig.com.br",
}


def normalize_phone(raw):
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None, None
    if digits.startswith(NON_GEOGRAPHIC_PREFIXES):
        return digits, "outro"
    if len(digits) in (12, 13) and digits.startswith("55"):
        digits = digits[2:]
    elif len(digits) in (11, 12) and digits.startswith("0"):
        digits = digits[1:]
    ddd, number = int(digits[:2] or 0), digits[2:]
    if ddd not in VALID_DDDS:
        return None, "invalido"
    if len(number) == 9 and number[0] == "9":
        return digits, "celular"
    if len(number) == 8 and number[0] in "2345":
        return digits, "fixo"
    return None, "invalido"


def format_phone(national):
    if not national:
        return None
    if national.startswith(NON_GEOGRAPHIC_PREFIXES):
        return f"{national[:4]} {national[4:7]} {national[7:]}"
    ddd, number = national[:2], national[2:]
    return f"({ddd}) {number[:-4]}-{number[-4:]}"


def whatsapp_url(national):
    return f"https://wa.me/55{national}"


def text_key(text):
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", plain.lower()).strip()


def normalize_uf(value):
    code = (value or "").strip().upper().removeprefix("BR-")
    return code if code in UFS else None


def normalize_url(raw):
    text = (raw or "").strip()
    if not text or " " in text:
        return None
    if "://" not in text:
        text = f"https://{text}"
    parts = urlsplit(text)
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        return None
    if (
        parts.scheme.lower() not in ("http", "https")
        or "." not in host
        or parts.username
        or parts.password
    ):
        return None
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    kept = [(key, value) for key, value in pairs if not key.lower().startswith(TRACKING_PARAMS)]
    query = parts.query if len(kept) == len(pairs) else urlencode(kept)
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path, query, parts.fragment))


def on_domain(host, domain):
    return host == domain or host.endswith(f".{domain}")


def classify_url(url):
    host = urlsplit(url).hostname or ""
    for domain, kind in URL_KINDS.items():
        if on_domain(host, domain):
            return kind
    return "propria"


def normalize_instagram(raw):
    text = (raw or "").strip()
    if "://" in text or "instagram.com" in text or "instagr.am" in text:
        url = normalize_url(text)
        return url if url and classify_url(url) == "instagram" else None
    match = INSTAGRAM_HANDLE.fullmatch(text)
    return match.group(1) if match else None


def is_free_site(url):
    host = urlsplit(url).hostname or ""
    return any(on_domain(host, domain) for domain in FREE_SITE_HOSTS)


def email_kind(email):
    _, at, domain = (email or "").strip().lower().rpartition("@")
    if not at or not domain:
        return None
    return "generico" if domain in GENERIC_EMAIL_DOMAINS else "proprio"
