import pytest

import zones


def all_districts():
    return [name for key in zones.ZONES for name in zones.districts(key)]


def test_the_five_zones_exist_in_this_order():
    assert list(zones.ZONES) == ["centro", "norte", "leste", "sul", "oeste"]


def test_labels_are_readable_names():
    assert zones.label("sul") == "Zona Sul"
    assert zones.label("centro") == "Centro"


def test_the_city_has_96_districts_and_none_is_in_two_zones():
    names = all_districts()

    assert len(names) == 96
    assert len(set(names)) == 96


@pytest.mark.parametrize("key", list(zones.ZONES))
def test_every_zone_has_districts_without_blank_names(key):
    assert zones.districts(key)
    assert all(name.strip() == name and name for name in zones.districts(key))


@pytest.mark.parametrize(
    "district, key",
    [
        ("Sé", "centro"),
        ("Pinheiros", "oeste"),
        ("Moema", "sul"),
        ("Tatuapé", "leste"),
        ("Santana", "norte"),
    ],
)
def test_well_known_districts_are_in_the_expected_zone(district, key):
    assert district in zones.districts(key)


def test_district_names_have_nothing_that_breaks_the_overpass_regex():
    assert not any(set(name) & set("^$.|?*+()[]{}\\\"") for name in all_districts())
