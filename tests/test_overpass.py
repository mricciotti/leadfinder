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


def test_parse_places_drops_places_that_already_have_a_website():
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
    assert [lead["name"] for lead in result["leads"]] == ["D"]


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
        "address": "Rua A, 10, Vila B",
        "instagram": "cantinaboa",
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
