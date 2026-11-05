import asyncio

import pytest

import overpass


def element(tags, kind="node", element_id=1, **extra):
    base = {"type": kind, "id": element_id, "tags": tags}
    if kind == "node":
        base.update({"lat": -23.56, "lon": -46.69})
    base.update(extra)
    return base


def test_build_query_uses_bbox_and_segment_filter():
    query = overpass.build_query("restaurante", (1.0, 2.0, 3.0, 4.0))

    assert 'nwr["amenity"="restaurant"]["name"](1.0,2.0,3.0,4.0);' in query
    assert query.endswith("out center tags;")


def test_build_query_unions_every_filter_of_a_segment():
    query = overpass.build_query("salao", (1.0, 2.0, 3.0, 4.0))

    assert query.count("nwr[") == 2


def test_build_query_rejects_unknown_segment():
    with pytest.raises(KeyError):
        overpass.build_query("inexistente", (1.0, 2.0, 3.0, 4.0))


def test_normalize_bbox_expands_tiny_areas_around_their_center():
    south, west, north, east = overpass.normalize_bbox(
        -23.5600, -46.6900, -23.5599, -46.6899
    )

    assert (south + north) / 2 == pytest.approx(-23.55995)
    assert (west + east) / 2 == pytest.approx(-46.68995)
    assert north - south == pytest.approx(2 * overpass.MIN_HALF_SPAN)
    assert east - west == pytest.approx(2 * overpass.MIN_HALF_SPAN)


def test_normalize_bbox_keeps_large_areas():
    bbox = overpass.normalize_bbox(-23.58, -46.72, -23.54, -46.66)

    assert bbox == pytest.approx((-23.58, -46.72, -23.54, -46.66))


def test_bbox_from_nominatim_reorders_to_south_west_north_east():
    results = [{"boundingbox": ["-23.58", "-23.54", "-46.72", "-46.66"]}]

    assert overpass.bbox_from_nominatim(results) == pytest.approx(
        (-23.58, -46.72, -23.54, -46.66)
    )


def test_bbox_from_nominatim_raises_when_nothing_found():
    with pytest.raises(overpass.PlaceNotFound):
        overpass.bbox_from_nominatim([])


def test_uf_from_nominatim_reads_the_state_code():
    results = [{"address": {"state": "São Paulo", "ISO3166-2-lvl4": "BR-SP"}}]

    assert overpass.uf_from_nominatim(results) == "SP"


def test_uf_from_nominatim_is_none_without_address_details():
    assert overpass.uf_from_nominatim([{"boundingbox": ["0", "1", "0", "1"]}]) is None


def test_parse_places_keeps_places_that_have_a_website():
    data = {
        "elements": [
            element({"name": "A", "website": "https://a.com"}, element_id=1),
            element({"name": "B", "contact:website": "https://b.com"}, element_id=2),
            element({"name": "C", "url": "https://c.com"}, element_id=3),
            element({"name": "D"}, element_id=4),
        ]
    }

    result = overpass.parse_places(data, "restaurante", "Pinheiros")

    assert result["total"] == 4
    assert [(lead["name"], lead["site_state"]) for lead in result["leads"]] == [
        ("A", "site_informado"),
        ("B", "site_informado"),
        ("C", "site_informado"),
        ("D", "sem_site_na_fonte"),
    ]
    assert result["leads"][1]["website"] == "https://b.com"


def parse_one(tags):
    return overpass.parse_places(
        {"elements": [element({"name": "Lugar", **tags})]}, "restaurante", "Pinheiros"
    )["leads"][0]


def test_parse_places_normalizes_the_website_and_drops_utm():
    lead = parse_one({"website": "www.lugar.com.br/?utm_source=osm"})

    assert lead["website"] == "https://www.lugar.com.br/"
    assert lead["site_state"] == "site_informado"


def test_parse_places_treats_an_instagram_website_as_social_only():
    lead = parse_one({"website": "https://instagram.com/lugar"})

    assert lead["website"] is None
    assert lead["site_state"] == "so_rede_social"
    assert lead["instagram"] == "https://instagram.com/lugar"
    assert lead["score"] == 1


def test_parse_places_keeps_the_instagram_tag_over_the_website_field():
    lead = parse_one(
        {"contact:instagram": "lugar", "website": "https://instagram.com/outro"}
    )

    assert lead["instagram"] == "lugar"
    assert lead["other_links"] == ["https://instagram.com/outro"]


def test_parse_places_treats_a_facebook_website_as_social_only():
    lead = parse_one({"contact:website": "https://m.facebook.com/lugar"})

    assert lead["site_state"] == "so_rede_social"
    assert lead["facebook"] == "https://m.facebook.com/lugar"


@pytest.mark.parametrize(
    "website",
    ["https://linktr.ee/lugar", "https://www.ifood.com.br/delivery/lugar", "https://wa.me/5511988887777"],
)
def test_parse_places_treats_link_pages_and_delivery_as_not_own_site(website):
    lead = parse_one({"website": website})

    assert lead["website"] is None
    assert lead["site_state"] == "so_rede_social"
    assert lead["other_links"] == [website]


def test_parse_places_ignores_an_invalid_website():
    lead = parse_one({"website": "não tem"})

    assert lead["website"] is None
    assert lead["site_state"] == "sem_site_na_fonte"


def test_parse_places_collects_email_facebook_and_other_links():
    lead = parse_one(
        {
            "email": "oi@lugar.com.br",
            "contact:facebook": "https://facebook.com/lugar",
            "contact:tiktok": "https://tiktok.com/@lugar",
            "contact:youtube": "https://youtube.com/@lugar",
        }
    )

    assert lead["email"] == "oi@lugar.com.br"
    assert lead["facebook"] == "https://facebook.com/lugar"
    assert lead["other_links"] == ["https://tiktok.com/@lugar", "https://youtube.com/@lugar"]
    assert lead["site_state"] == "sem_site_na_fonte"


def test_parse_places_takes_city_and_uf_from_the_address():
    lead = overpass.parse_places(
        {"elements": [element({"name": "Lugar", "addr:city": "Osasco", "addr:state": "SP"})]},
        "restaurante",
        "Pinheiros",
        "São Paulo",
        "RJ",
    )["leads"][0]

    assert (lead["city"], lead["uf"]) == ("Osasco", "SP")


def test_parse_places_falls_back_to_the_searched_city_and_uf():
    lead = overpass.parse_places(
        {"elements": [element({"name": "Lugar", "addr:state": "São Paulo"})]},
        "restaurante",
        "Pinheiros",
        "São Paulo",
        "SP",
    )["leads"][0]

    assert (lead["city"], lead["uf"]) == ("São Paulo", "SP")


def test_parse_places_normalizes_the_phone():
    lead = parse_one({"phone": "+55 11 98888-7777"})

    assert lead["phone"] == "+55 11 98888-7777"
    assert (lead["phone_national"], lead["phone_kind"]) == ("11988887777", "celular")


def test_parse_places_ignores_elements_without_a_name():
    data = {"elements": [element({"amenity": "restaurant"}), element({"name": ""})]}

    result = overpass.parse_places(data, "restaurante", "Pinheiros")

    assert result == {"total": 0, "leads": []}


def test_parse_places_builds_lead_fields():
    tags = {
        "name": "Cantina Boa",
        "phone": "+55 11 3333-4444",
        "addr:street": "Rua A",
        "addr:housenumber": "10",
        "addr:suburb": "Vila B",
        "contact:instagram": "cantinaboa",
    }

    lead = overpass.parse_places(
        {"elements": [element(tags, element_id=77)]}, "restaurante", "Pinheiros"
    )["leads"][0]

    assert lead == {
        "id": "node-77",
        "name": "Cantina Boa",
        "segment": "restaurante",
        "neighborhood": "Pinheiros",
        "phone": "+55 11 3333-4444",
        "phone_national": "1133334444",
        "phone_kind": "fixo",
        "address": "Rua A, 10, Vila B",
        "city": None,
        "uf": None,
        "email": None,
        "instagram": "cantinaboa",
        "facebook": None,
        "other_links": [],
        "website": None,
        "site_state": "sem_site_na_fonte",
        "lat": -23.56,
        "lon": -46.69,
        "score": 5,
    }


def test_parse_places_scores_a_complete_listing_at_the_maximum():
    tags = {
        "name": "Completa",
        "phone": "+55 11 3333-4444",
        "opening_hours": "Mo-Su 12:00-23:00",
        "addr:street": "Rua A",
        "contact:instagram": "completa",
    }

    lead = overpass.parse_places(
        {"elements": [element(tags)]}, "restaurante", "Pinheiros"
    )["leads"][0]

    assert lead["score"] == 6


def test_parse_places_scores_a_bare_listing_at_zero():
    lead = overpass.parse_places(
        {"elements": [element({"name": "Nua"})]}, "restaurante", "Pinheiros"
    )["leads"][0]

    assert lead["score"] == 0
    assert lead["phone"] is None
    assert lead["address"] is None


def test_parse_places_uses_center_for_ways():
    way = element(
        {"name": "Galpão"},
        kind="way",
        element_id=9,
        center={"lat": -23.1, "lon": -46.2},
    )

    lead = overpass.parse_places({"elements": [way]}, "bar", "Mooca")["leads"][0]

    assert lead["id"] == "way-9"
    assert (lead["lat"], lead["lon"]) == (-23.1, -46.2)


def test_parse_places_keeps_only_the_first_phone():
    tags = {"name": "Dois", "phone": "+55 11 1111-1111; +55 11 2222-2222"}

    lead = overpass.parse_places(
        {"elements": [element(tags)]}, "bar", "Mooca"
    )["leads"][0]

    assert lead["phone"] == "+55 11 1111-1111"


def test_parse_places_falls_back_to_other_phone_tags():
    tags = {"name": "Celular", "contact:mobile": "+55 11 98888-7777"}

    lead = overpass.parse_places(
        {"elements": [element(tags)]}, "bar", "Mooca"
    )["leads"][0]

    assert lead["phone"] == "+55 11 98888-7777"


import httpx

NOMINATIM_ANSWER = [
    {
        "boundingbox": ["-23.63", "-23.60", "-46.66", "-46.62"],
        "address": {"ISO3166-2-lvl4": "BR-SP"},
    }
]
OVERPASS_ANSWER = {"elements": [element({"name": "Cantina"})]}


def fake_servers(overpass_statuses, nominatim_status=200):
    calls = {"overpass": 0, "nominatim": 0}
    waits = []

    def handler(request):
        if "nominatim" in request.url.host:
            calls["nominatim"] += 1
            return httpx.Response(nominatim_status, json=NOMINATIM_ANSWER)
        status = overpass_statuses[min(calls["overpass"], len(overpass_statuses) - 1)]
        calls["overpass"] += 1
        if status == "timeout":
            raise httpx.ReadTimeout("lento", request=request)
        return httpx.Response(status, json=OVERPASS_ANSWER if status == 200 else {})

    async def sleep(seconds):
        waits.append(seconds)

    return calls, waits, httpx.MockTransport(handler), sleep


def run_search(transport, sleep):
    return asyncio.run(
        overpass.search("restaurante", "Saúde", "São Paulo", transport=transport, sleep=sleep)
    )


@pytest.mark.parametrize("status", [429, 502, 503, 504])
def test_search_retries_a_busy_overpass_until_it_answers(status):
    calls, waits, transport, sleep = fake_servers([status, status, 200])

    result = run_search(transport, sleep)

    assert [lead["name"] for lead in result["leads"]] == ["Cantina"]
    assert calls["overpass"] == 3
    assert waits == list(overpass.RETRY_WAITS[:2])


def test_search_geocodes_only_once_while_retrying():
    calls, _, transport, sleep = fake_servers([502, 200])

    run_search(transport, sleep)

    assert calls["nominatim"] == 1


def test_search_retries_a_timeout():
    calls, _, transport, sleep = fake_servers(["timeout", 200])

    run_search(transport, sleep)

    assert calls["overpass"] == 2


def test_search_gives_up_after_the_last_attempt():
    calls, waits, transport, sleep = fake_servers([502])

    with pytest.raises(httpx.HTTPStatusError):
        run_search(transport, sleep)

    assert calls["overpass"] == len(overpass.RETRY_WAITS) + 1
    assert waits == list(overpass.RETRY_WAITS)


@pytest.mark.parametrize("status", [400, 404])
def test_search_does_not_retry_a_request_error(status):
    calls, waits, transport, sleep = fake_servers([status])

    with pytest.raises(httpx.HTTPStatusError):
        run_search(transport, sleep)

    assert calls["overpass"] == 1
    assert waits == []


def test_search_does_not_retry_when_everything_works():
    calls, waits, transport, sleep = fake_servers([200])

    run_search(transport, sleep)

    assert calls["overpass"] == 1
    assert waits == []


NEW_SEGMENTS = {
    "clinica": ("Clínica e consultório", {("amenity", "doctors"), ("amenity", "clinic"), ("healthcare", "doctor"), ("healthcare", "clinic")}),
    "oficina": ("Oficina mecânica", {("shop", "car_repair")}),
    "petshop": ("Pet shop", {("shop", "pet"), ("shop", "pet_grooming")}),
    "veterinario": ("Veterinário", {("amenity", "veterinary")}),
    "confeitaria": ("Confeitaria e doceria", {("shop", "pastry"), ("shop", "confectionery")}),
    "sorveteria": ("Sorveteria", {("amenity", "ice_cream")}),
    "otica": ("Ótica", {("shop", "optician")}),
    "imobiliaria": ("Imobiliária", {("office", "estate_agent")}),
}


@pytest.mark.parametrize("key", NEW_SEGMENTS)
def test_new_segments_have_the_verified_osm_tags(key):
    label, tags = NEW_SEGMENTS[key]

    assert overpass.SEGMENTS[key][0] == label
    assert set(overpass.SEGMENTS[key][1]) == tags


@pytest.mark.parametrize("key", NEW_SEGMENTS)
def test_new_segments_build_a_query_for_every_tag(key):
    query = overpass.build_query(key, (-23.6, -46.7, -23.5, -46.6))

    for tag_key, tag_value in NEW_SEGMENTS[key][1]:
        assert f'nwr["{tag_key}"="{tag_value}"]["name"]' in query


def test_every_segment_has_a_label_and_at_least_one_tag():
    for key, (label, tags) in overpass.SEGMENTS.items():
        assert key == key.lower() and key.isascii() and key.isalpha()
        assert label.strip()
        assert tags and all(len(tag) == 2 for tag in tags)


def test_segment_labels_are_unique():
    labels = [label for label, _ in overpass.SEGMENTS.values()]

    assert len(labels) == len(set(labels))
