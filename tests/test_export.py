import csv
import io
from contextlib import closing
from datetime import date

import pytest

import db
import export
import scoring
from test_db import lead

LEADS_HEADER = [
    "Nome",
    "Categoria",
    "Telefone",
    "WhatsApp",
    "Situação do WhatsApp",
    "Link do WhatsApp",
    "E-mail",
    "Tipo do e-mail",
    "Website",
    "Instagram",
    "Facebook",
    "Outras redes",
    "Endereço",
    "Bairro",
    "Cidade",
    "UF",
    "Situação do site",
    "Ofertas",
    "Prioridade",
    "Nota de contato",
    "Nota de oportunidade",
    "Motivos",
    "Origem",
    "Última verificação (UTC)",
]

FIXO = {"phone": "+55 11 3815-2600", "phone_national": "1138152600", "phone_kind": "fixo"}
CELULAR = {"phone": "+55 11 98888-7777", "phone_national": "11988887777", "phone_kind": "celular"}


def saved(tmp_path, one_lead, **changes):
    with closing(db.connect(tmp_path / "export.db")) as conn:
        db.add_leads(conn, [one_lead])
        if changes:
            db.update_lead(conn, one_lead["id"], **changes)
        return scoring.ranked(db.list_leads(conn))


def parse(content):
    text = content.decode("utf-8").removeprefix("﻿")
    return list(csv.reader(io.StringIO(text), delimiter=";"))


def first_row(tmp_path, one_lead, **changes):
    header, row = parse(export.leads_csv(saved(tmp_path, one_lead, **changes)))[:2]
    return dict(zip(header, row))


def test_leads_csv_has_the_commercial_columns_in_order(tmp_path):
    header = parse(export.leads_csv(saved(tmp_path, lead())))[0]

    assert header == LEADS_HEADER
    assert not any("avalia" in column.lower() for column in header)


def test_csv_starts_with_bom_and_uses_semicolons(tmp_path):
    content = export.leads_csv(saved(tmp_path, lead()))

    assert content.startswith(b"\xef\xbb\xbf")
    assert content.decode("utf-8").splitlines()[0].count(";") == len(LEADS_HEADER) - 1


def test_portuguese_characters_survive(tmp_path):
    row = first_row(tmp_path, lead(name="Pão de Açúcar Café", neighborhood="Saúde"))

    assert row["Nome"] == "Pão de Açúcar Café"
    assert row["Bairro"] == "Saúde"


def test_leads_csv_row_values(tmp_path):
    row = first_row(
        tmp_path,
        lead(
            **CELULAR,
            email="cantina@gmail.com",
            site_state="so_rede_social",
            instagram="https://instagram.com/cantina",
            other_links=["https://linktr.ee/cantina"],
        ),
    )

    assert row["Categoria"] == "Restaurante"
    assert row["Telefone"] == "(11) 98888-7777"
    assert row["WhatsApp"] == "(11) 98888-7777"
    assert row["Situação do WhatsApp"] == "potencial (celular, não confirmado)"
    assert row["Link do WhatsApp"] == "https://wa.me/5511988887777"
    assert row["Tipo do e-mail"] == "genérico"
    assert row["Outras redes"] == "https://linktr.ee/cantina"
    assert row["Situação do site"] == "Só rede social, página de links ou delivery"
    assert row["Ofertas"] == "Página própria | Cardápio digital com QR code"
    assert row["Prioridade"] == "alta"
    assert "Instagram identificado" in row["Motivos"].split(" | ")
    assert row["Origem"] == "OpenStreetMap"
    assert row["Última verificação (UTC)"] == ""


def test_missing_data_stays_empty(tmp_path):
    row = first_row(tmp_path, lead())

    for column in ("Telefone", "WhatsApp", "Link do WhatsApp", "E-mail", "Website", "Instagram"):
        assert row[column] == ""


def test_landline_has_no_whatsapp_link(tmp_path):
    row = first_row(tmp_path, lead(**FIXO))

    assert row["Telefone"] == "(11) 3815-2600"
    assert row["WhatsApp"] == row["Link do WhatsApp"] == ""


def test_manual_check_shows_in_the_export(tmp_path):
    row = first_row(tmp_path, lead(), manual_whatsapp="1138152600", absence_confirmed=True)

    assert row["WhatsApp"] == "(11) 3815-2600"
    assert row["Situação do WhatsApp"] == "informado por você"
    assert row["Situação do site"] == "Sem site (confirmado manualmente)"
    assert row["Origem"] == "OpenStreetMap + checagem manual"
    assert row["Última verificação (UTC)"]


@pytest.mark.parametrize(
    "value, expected",
    [
        ('=HYPERLINK("http://x","clique")', '\'=HYPERLINK("http://x","clique")'),
        ("+cmd|' /C calc'!A0", "'+cmd|' /C calc'!A0"),
        ("@SUM(1+1)", "'@SUM(1+1)"),
        ("-2+3", "'-2+3"),
        ("\tcmd", "'\tcmd"),
        ("\rcmd", "'\rcmd"),
        ("+55 11 3815-2600", "+55 11 3815-2600"),
        ("(11) 3815-2600", "(11) 3815-2600"),
        ("Cantina", "Cantina"),
        (None, ""),
    ],
)
def test_csv_safe(value, expected):
    assert export.csv_safe(value) == expected


def test_formula_in_a_name_is_neutralized_in_the_file(tmp_path):
    row = first_row(tmp_path, lead(name='=HYPERLINK("http://x")'))

    assert row["Nome"] == '\'=HYPERLINK("http://x")'


def test_phone_with_plus_is_not_corrupted_in_the_full_csv(tmp_path):
    header, row = parse(export.full_csv(saved(tmp_path, lead(**FIXO))))[:2]

    assert dict(zip(header, row))["phone"] == "+55 11 3815-2600"


def test_full_csv_has_every_stored_column_and_the_evaluation(tmp_path):
    header, row = parse(
        export.full_csv(saved(tmp_path, lead(other_links=["https://a.com", "https://b.com"])))
    )[:2]
    values = dict(zip(header, row))

    for column in ("id", "name", "status", "notes", "site_state", "manual_phone", "favorite"):
        assert column in header
    for column in ("priority", "contact_level", "opportunity_level", "offers", "reasons"):
        assert column in header
    assert values["other_links"] == "https://a.com | https://b.com"
    assert "evaluation" not in header


def test_file_name_uses_the_search_and_the_date():
    wanted = {"segment": "restaurante", "neighborhood": "Saúde", "city": None}
    nothing = {"segment": None, "neighborhood": None, "city": None}

    assert export.file_name("leads", wanted, date(2026, 11, 3)) == "leads-restaurante-saude-2026-11-03.csv"
    assert export.file_name("completo", nothing, date(2026, 11, 3)) == "leads-completo-2026-11-03.csv"


@pytest.mark.parametrize("points, expected", [(0, "0 pontos"), (1, "1 ponto"), (5, "5 pontos")])
def test_points_label(points, expected):
    assert export.points_label(points) == expected
