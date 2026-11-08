import json
from contextlib import closing
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from fastapi.testclient import TestClient

import db
import main
from test_db import lead

NOW = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
BASE = "https://previas.test"
FIXO = {"phone": "+55 11 3815-2600", "phone_national": "1138152600", "phone_kind": "fixo"}
CELULAR = {"phone": "+55 11 98015-0754", "phone_national": "11980150754", "phone_kind": "celular"}


class App:
    def __init__(self, tmp_path, base=BASE, now=NOW):
        self.path = tmp_path / "api.db"
        self.vitrines = tmp_path / "publicadas"
        self.clientes = tmp_path / "clientes"
        self.client = TestClient(
            main.create_app(
                self.path,
                now=lambda: now,
                vitrines_dir=self.vitrines,
                clientes_dir=self.clientes,
                public_base=base,
            )
        )

    def seed(self, *leads):
        with closing(db.connect(self.path)) as conn:
            db.add_leads(conn, list(leads))

    def sql(self, statement, *values):
        with closing(db.connect(self.path)) as conn:
            conn.execute(statement, values)
            conn.commit()

    def vitrine(self, lead_id="node-1"):
        response = self.client.post(f"/api/leads/{lead_id}/vitrine")
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture
def app(tmp_path):
    instance = App(tmp_path)
    instance.seed(lead("node-1", name="Janis Bull Barbearia", **CELULAR))
    return instance


def test_creating_a_vitrine_returns_the_slug_and_the_urls(app):
    vitrine = app.vitrine()

    assert vitrine["slug"] == "janis-bull-barbearia"
    assert vitrine["local_url"] == "/s/janis-bull-barbearia"
    assert vitrine["public_url"] == "https://previas.test/janis-bull-barbearia/"
    assert (vitrine["approved"], vitrine["exported_at"], vitrine["content"]) == (False, None, {})


def test_creating_twice_returns_the_same_vitrine(app):
    first = app.vitrine()
    second = app.vitrine()

    assert first["slug"] == second["slug"]
    with closing(db.connect(app.path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM vitrines").fetchone()[0] == 1


def test_two_leads_with_the_same_name_get_different_slugs(app):
    app.seed(lead("node-2", name="Janis Bull Barbearia", lat=-23.7, neighborhood="Mooca", **FIXO))

    slugs = {app.vitrine("node-1")["slug"], app.vitrine("node-2")["slug"]}

    assert slugs == {"janis-bull-barbearia", "janis-bull-barbearia-mooca"}


def test_vitrine_for_an_unknown_lead_is_404(app):
    assert app.client.post("/api/leads/node-404/vitrine").status_code == 404


def test_without_a_public_base_the_vitrine_has_only_the_local_url(tmp_path):
    instance = App(tmp_path, base=None)
    instance.seed(lead("node-1", **CELULAR))

    assert instance.vitrine()["public_url"] is None


def test_an_invalid_public_base_is_ignored(tmp_path):
    instance = App(tmp_path, base="javascript:alert(1)")
    instance.seed(lead("node-1", **CELULAR))

    assert instance.vitrine()["public_url"] is None


@pytest.mark.parametrize("blocked", ["descartado", "nao_contatar"])
def test_discarded_or_do_not_contact_leads_get_no_vitrine(app, blocked):
    if blocked == "descartado":
        app.client.patch("/api/leads/node-1", json={"status": "descartado"})
    else:
        app.client.patch("/api/leads/node-1", json={"do_not_contact": True})

    response = app.client.post("/api/leads/node-1/vitrine")

    assert response.status_code == 409
    assert "não contatar" in response.json()["detail"]
    with closing(db.connect(app.path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM vitrines").fetchone()[0] == 0


def test_local_preview_renders_the_vitrine_with_the_preview_banner(app):
    slug = app.vitrine()["slug"]

    response = app.client.get(f"/s/{slug}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert "Prévia criada para <b>Janis Bull Barbearia</b>" in response.text
    assert "wa.me/5511980150754" in response.text


def test_approving_removes_the_banner_and_noindex_from_the_preview(app):
    slug = app.vitrine()["slug"]
    app.client.patch(f"/api/vitrines/{slug}", json={"approved": True})

    page = app.client.get(f"/s/{slug}").text

    assert "Prévia criada para" not in page and 'name="robots"' not in page


@pytest.mark.parametrize("slug", ["naoexiste", "a%20b", "A-B-C", "ab", "x" * 61, "..%2Fx", "%2e%2e%2fx", "a%2Fb"])
def test_preview_of_an_unknown_or_malformed_slug_is_404(app, slug):
    assert app.client.get(f"/s/{slug}").status_code == 404


def test_preview_reflects_later_changes_to_the_lead(app):
    slug = app.vitrine()["slug"]
    app.client.patch("/api/leads/node-1", json={"manual_instagram": "@janis.bull"})

    assert "https://instagram.com/janis.bull" in app.client.get(f"/s/{slug}").text


def test_editing_the_vitrine_changes_the_page_and_clears_with_empty_values(app):
    slug = app.vitrine()["slug"]

    edited = app.client.patch(
        f"/api/vitrines/{slug}",
        json={
            "hours": "Segunda a sábado, 10h às 20h",
            "address": "Rua Doutor Nicolau de Sousa Queirós, 73",
            "category": "Barbearia",
            "services": [{"name": "Corte social", "text": "Na tesoura"}],
        },
    )

    assert edited.status_code == 200
    page = app.client.get(f"/s/{slug}").text
    assert "Segunda a sábado, 10h às 20h" in page and "Queirós, 73" in page
    assert "Corte social" in page and "Na tesoura" in page
    services = page.split('id="servicos"')[1].split('id="como"')[0]
    assert "MODELO" not in services

    cleared = app.client.patch(f"/api/vitrines/{slug}", json={"hours": "", "services": []})

    assert "hours" not in cleared.json()["content"] and "services" not in cleared.json()["content"]
    assert "Segunda a sábado" not in app.client.get(f"/s/{slug}").text


def test_editing_keeps_the_fields_that_were_not_sent(app):
    slug = app.vitrine()["slug"]
    app.client.patch(f"/api/vitrines/{slug}", json={"hours": "10h às 20h"})

    content = app.client.patch(f"/api/vitrines/{slug}", json={"category": "Barbearia"}).json()["content"]

    assert content == {"hours": "10h às 20h", "category": "Barbearia"}


def test_editing_a_restaurant_menu_shows_the_menu_section(tmp_path):
    instance = App(tmp_path)
    instance.seed(lead("node-1", name="Cantina Boa", segment="restaurante", **CELULAR))
    slug = instance.vitrine()["slug"]

    instance.client.patch(f"/api/vitrines/{slug}", json={"menu": [{"name": "Feijoada", "price": "R$ 40"}]})

    page = instance.client.get(f"/s/{slug}").text
    assert "CARDÁPIO." in page and "Feijoada" in page and "R$ 40" in page


@pytest.mark.parametrize(
    "body",
    [
        {"services": [{"name": "x" * 61}]},
        {"services": [{"name": f"s{i}"} for i in range(9)]},
        {"services": [{"name": "ok", "text": "t" * 161}]},
        {"menu": [{"name": "ok", "price": "p" * 21}]},
        {"hours": "h" * 121},
        {"category": "c" * 41},
        {"address": "a" * 161},
        {"name": "n" * 81},
    ],
)
def test_vitrine_edits_are_validated(app, body):
    slug = app.vitrine()["slug"]

    assert app.client.patch(f"/api/vitrines/{slug}", json=body).status_code == 422


def test_editing_an_unknown_vitrine_is_404(app):
    assert app.client.patch("/api/vitrines/naoexiste", json={"hours": "x"}).status_code == 404


def test_export_writes_index_html_inside_the_vitrines_folder(app):
    slug = app.vitrine()["slug"]

    response = app.client.post(f"/api/vitrines/{slug}/export")

    assert response.status_code == 200
    target = app.vitrines / slug / "index.html"
    assert target.exists()
    assert response.json()["path"] == str(target.resolve())
    assert response.json()["exported_at"]
    assert target.read_text(encoding="utf-8") == app.client.get(f"/s/{slug}").text
    assert [item.name for item in app.vitrines.iterdir()] == [slug]


def test_export_of_an_approved_vitrine_has_no_banner_and_no_noindex(app):
    slug = app.vitrine()["slug"]
    app.client.patch(f"/api/vitrines/{slug}", json={"approved": True})

    app.client.post(f"/api/vitrines/{slug}/export")

    page = (app.vitrines / slug / "index.html").read_text(encoding="utf-8")
    assert "Prévia criada para" not in page and "noindex" not in page


def test_export_keeps_unix_newlines_so_the_script_hash_stays_valid(app):
    slug = app.vitrine()["slug"]
    app.client.post(f"/api/vitrines/{slug}/export")

    raw = (app.vitrines / slug / "index.html").read_bytes()

    assert b"\r\n" not in raw


@pytest.mark.parametrize("slug", ["..", "%2e%2e", "..%2Fx", "a%2Fb", "naoexiste", "ab"])
def test_export_with_a_malicious_or_unknown_slug_is_refused_and_writes_nothing(app, tmp_path, slug):
    before = sorted(path.name for path in tmp_path.rglob("*"))

    response = app.client.post(f"/api/vitrines/{slug}/export")

    assert response.status_code in (404, 405)
    assert sorted(path.name for path in tmp_path.rglob("*")) == before


def test_export_refuses_a_slug_stored_with_a_path_in_it(app, tmp_path):
    app.vitrine()
    app.sql("UPDATE vitrines SET slug = '../fora'")

    response = app.client.post("/api/vitrines/..%2Ffora/export")

    assert response.status_code in (404, 405)
    assert not (tmp_path / "fora").exists()


@pytest.mark.parametrize("blocked", ["descartado", "nao_contatar"])
def test_export_and_folder_are_refused_after_the_lead_is_discarded_or_marked(app, blocked):
    slug = app.vitrine()["slug"]
    if blocked == "descartado":
        app.client.patch("/api/leads/node-1", json={"status": "descartado"})
    else:
        app.client.patch("/api/leads/node-1", json={"do_not_contact": True})

    assert app.client.post(f"/api/vitrines/{slug}/export").status_code == 409
    assert app.client.post(f"/api/vitrines/{slug}/folder").status_code == 409
    assert not app.vitrines.exists() and not app.clientes.exists()


def test_client_folder_has_the_two_files_and_no_invented_data(app):
    slug = app.vitrine()["slug"]

    response = app.client.post(f"/api/vitrines/{slug}/folder")

    assert response.status_code == 200
    folder = app.clientes / slug
    assert sorted(path.name for path in folder.iterdir()) == ["PROMPT.md", "dados.json"]
    data = json.loads((folder / "dados.json").read_text(encoding="utf-8"))
    assert data["campos"]["telefone"]["valor"] == "(11) 98015-0754"
    assert {"endereco", "instagram", "horario"} <= set(data["campos_ausentes"]) | set(data["campos"])
    assert "Use só os dados" in (folder / "PROMPT.md").read_text(encoding="utf-8")


def test_client_folder_rewrites_the_data_but_keeps_a_prompt_you_edited(app):
    slug = app.vitrine()["slug"]
    app.client.post(f"/api/vitrines/{slug}/folder")
    folder = app.clientes / slug
    (folder / "PROMPT.md").write_text("meu prompt editado", encoding="utf-8")
    app.client.patch(f"/api/vitrines/{slug}", json={"hours": "10h às 20h"})

    again = app.client.post(f"/api/vitrines/{slug}/folder").json()

    assert again["written"] == ["dados.json"]
    assert (folder / "PROMPT.md").read_text(encoding="utf-8") == "meu prompt editado"
    assert json.loads((folder / "dados.json").read_text(encoding="utf-8"))["campos"]["horario"]["valor"] == "10h às 20h"


def message(app, lead_id="node-1", **params):
    return app.client.get(f"/api/leads/{lead_id}/message", params=params)


def test_message_asks_for_the_vitrine_first(app):
    body = message(app).json()

    assert body["text"] is None and "Crie a vitrine" in body["reason"]


def test_message_asks_for_the_public_base_when_it_is_not_configured(tmp_path):
    instance = App(tmp_path, base=None)
    instance.seed(lead("node-1", **CELULAR))
    instance.vitrine()

    body = message(instance).json()

    assert body["text"] is None and body["link_ready"] is False and "LEADFINDER_VITRINE_BASE" in body["reason"]


def test_message_carries_the_public_link_and_the_lead_data(app):
    app.vitrine()

    body = message(app).json()

    assert body["link"] == "https://previas.test/janis-bull-barbearia/"
    assert body["link_ready"] is True and body["warnings"] == []
    assert body["text"].startswith("Oi, tudo bem? Meu nome é Matheus.")
    assert body["text"].endswith(body["link"])
    assert "Janis Bull Barbearia" in body["text"] and "em Vila Mariana" not in body["text"].replace("Pinheiros", "")
    assert body["case"] == "sem_site"
    assert (body["can_whatsapp"], body["whatsapp"]) == (True, "5511980150754")


def test_message_case_follows_the_offer_of_the_lead(tmp_path):
    instance = App(tmp_path)
    instance.seed(lead("node-1", name="So Insta", site_state="so_rede_social", instagram="https://instagram.com/x", **CELULAR))
    instance.vitrine()

    assert message(instance).json()["case"] == "so_rede_social"


def test_follow_up_message_uses_the_follow_up_text(app):
    app.vitrine()

    body = message(app, kind="follow_up").json()

    assert body["case"] == "follow_up" and "é só me avisar que eu não escrevo mais" in body["text"]


def test_a_landline_lead_cannot_use_whatsapp(tmp_path):
    instance = App(tmp_path)
    instance.seed(lead("node-1", **FIXO))
    instance.vitrine()

    body = message(instance).json()

    assert body["can_whatsapp"] is False and body["whatsapp"] == ""
    assert body["text"]


def test_message_is_refused_for_a_do_not_contact_lead(app):
    app.vitrine()
    app.client.patch("/api/leads/node-1", json={"do_not_contact": True})

    assert message(app).status_code == 409


def test_message_for_an_unknown_lead_is_404(app):
    assert message(app, "node-404").status_code == 404


def test_message_reports_whether_the_vitrine_was_exported(app):
    slug = app.vitrine()["slug"]
    assert message(app).json()["exported"] is False

    app.client.post(f"/api/vitrines/{slug}/export")

    assert message(app).json()["exported"] is True


def test_asking_for_the_message_never_changes_the_stage(app):
    app.vitrine()

    message(app)

    assert app.client.get("/api/leads").json()[0]["status"] == "novo"
    with closing(db.connect(app.path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM status_changes").fetchone()[0] == 0


def test_marking_sent_changes_the_stage_records_the_date_and_counts_for_today(app):
    app.vitrine()
    assert app.client.get("/api/today").json() == {"sent": 0, "limit": 15, "remaining": 15}

    sent = app.client.patch("/api/leads/node-1", json={"status": "contatado"})

    assert sent.json()["status"] == "contatado"
    with closing(db.connect(app.path)) as conn:
        assert conn.execute("SELECT status FROM status_changes").fetchone()[0] == "contatado"
    app.sql("UPDATE status_changes SET changed_at = '2026-11-08 14:00:00'")
    assert app.client.get("/api/today").json() == {"sent": 1, "limit": 15, "remaining": 14}


def queue_ids(app, **params):
    return [item["id"] for item in app.client.get("/api/leads", params={"queue": "hoje", **params}).json()]


def test_leads_carry_their_vitrine_slug(app):
    assert app.client.get("/api/leads").json()[0]["vitrine_slug"] is None

    app.vitrine()

    assert app.client.get("/api/leads").json()[0]["vitrine_slug"] == "janis-bull-barbearia"


def test_queue_has_only_unapproached_reachable_leads_with_a_vitrine(tmp_path):
    instance = App(tmp_path)
    instance.seed(
        lead("node-1", name="Com Vitrine", **CELULAR),
        lead("node-2", name="Sem Vitrine", lat=-23.6, **CELULAR),
        lead("node-3", name="Sem Contato", lat=-23.7),
        lead("node-4", name="Ja Contatado", lat=-23.8, **CELULAR),
    )
    for lead_id in ("node-1", "node-3", "node-4"):
        instance.vitrine(lead_id)
    instance.client.patch("/api/leads/node-4", json={"status": "contatado"})

    assert queue_ids(instance) == ["node-1"]


def test_queue_accepts_prospecto_leads(app):
    app.vitrine()
    app.client.patch("/api/leads/node-1", json={"status": "prospecto"})

    assert queue_ids(app) == ["node-1"]


def test_queue_drops_a_lead_marked_do_not_contact(app):
    app.vitrine()
    app.client.patch("/api/leads/node-1", json={"do_not_contact": True})

    assert queue_ids(app) == []


def test_queue_shows_only_what_is_left_of_the_daily_limit(tmp_path):
    instance = App(tmp_path)
    instance.seed(*[lead(f"node-{i}", name=f"Negocio {i}", lat=-23.5 - i / 100, **CELULAR) for i in range(20)])
    for i in range(20):
        instance.vitrine(f"node-{i}")
    for i in range(5):
        instance.client.patch(f"/api/leads/node-{i}", json={"status": "contatado"})
    instance.sql("UPDATE status_changes SET changed_at = '2026-11-08 14:00:00'")

    assert len(queue_ids(instance)) == 10
    assert instance.client.get("/api/today").json()["remaining"] == 10


def test_queue_is_empty_once_the_daily_limit_is_reached(tmp_path):
    instance = App(tmp_path)
    instance.seed(*[lead(f"node-{i}", name=f"Negocio {i}", lat=-23.5 - i / 100, **CELULAR) for i in range(17)])
    for i in range(17):
        instance.vitrine(f"node-{i}")
    for i in range(15):
        instance.client.patch(f"/api/leads/node-{i}", json={"status": "contatado"})
    instance.sql("UPDATE status_changes SET changed_at = '2026-11-08 14:00:00'")

    assert queue_ids(instance) == []


def test_yesterdays_contacts_do_not_count_against_todays_limit(tmp_path):
    instance = App(tmp_path)
    instance.seed(*[lead(f"node-{i}", name=f"Negocio {i}", lat=-23.5 - i / 100, **CELULAR) for i in range(16)])
    for i in range(16):
        instance.vitrine(f"node-{i}")
    for i in range(15):
        instance.client.patch(f"/api/leads/node-{i}", json={"status": "contatado"})
    instance.sql("UPDATE status_changes SET changed_at = '2026-11-07 14:00:00'")

    assert queue_ids(instance) == ["node-15"]


def test_queue_works_together_with_the_other_filters_and_the_export(app):
    app.vitrine()

    assert queue_ids(app, phone="true") == ["node-1"]
    assert queue_ids(app, email="true") == []
    csv = app.client.get("/api/export/leads", params={"queue": "hoje"})
    assert csv.status_code == 200 and "Janis Bull Barbearia" in csv.content.decode("utf-8-sig")


def contacted_days_ago(app, lead_id, when):
    app.client.patch(f"/api/leads/{lead_id}", json={"status": "contatado"})
    app.sql("UPDATE status_changes SET changed_at = ? WHERE lead_id = ?", when, lead_id)


def follow_up_ids(app):
    return [item["id"] for item in app.client.get("/api/leads", params={"queue": "follow_up"}).json()]


def test_follow_up_list_has_leads_contacted_three_or_more_days_ago(app):
    app.seed(lead("node-2", name="Recente", lat=-23.6, **CELULAR))
    contacted_days_ago(app, "node-1", "2026-11-05 15:00:00")
    contacted_days_ago(app, "node-2", "2026-11-05 15:01:00")

    assert follow_up_ids(app) == ["node-1"]


def test_follow_up_once_sent_never_comes_back(app):
    contacted_days_ago(app, "node-1", "2026-11-01 10:00:00")
    assert follow_up_ids(app) == ["node-1"]

    sent = app.client.patch("/api/leads/node-1", json={"follow_up_sent": True}).json()

    assert sent["follow_up_at"]
    assert follow_up_ids(app) == []
    again = app.client.patch("/api/leads/node-1", json={"follow_up_sent": True}).json()
    assert again["follow_up_at"] == sent["follow_up_at"]


def test_follow_up_leaves_out_a_do_not_contact_lead(app):
    contacted_days_ago(app, "node-1", "2026-11-01 10:00:00")
    app.client.patch("/api/leads/node-1", json={"do_not_contact": True})

    assert follow_up_ids(app) == []


def test_follow_up_leaves_out_leads_that_already_answered(app):
    contacted_days_ago(app, "node-1", "2026-11-01 10:00:00")
    app.client.patch("/api/leads/node-1", json={"status": "respondeu"})

    assert follow_up_ids(app) == []


def test_do_not_contact_is_reversible_and_dated(app):
    marked = app.client.patch("/api/leads/node-1", json={"do_not_contact": True}).json()
    undone = app.client.patch("/api/leads/node-1", json={"do_not_contact": False}).json()

    assert marked["do_not_contact_at"] and undone["do_not_contact_at"] is None
    assert app.client.post("/api/leads/node-1/vitrine").status_code == 200


def test_unknown_queue_value_is_rejected(app):
    assert app.client.get("/api/leads", params={"queue": "tudo"}).status_code == 422


def test_a_do_not_contact_lead_already_saved_never_comes_back_as_recommended(tmp_path):
    instance = App(tmp_path)
    instance.seed(lead("node-1", name="Ja Salvo", **CELULAR))
    instance.client.patch("/api/leads/node-1", json={"do_not_contact": True})

    async def again(segment, neighborhood, city, **extra):
        return {"total": 1, "leads": [lead("node-1", name="Ja Salvo", **CELULAR)]}

    searching = TestClient(main.create_app(instance.path, again))
    found = searching.post("/api/search", json={"segment": "restaurante", "neighborhood": "Pinheiros"}).json()

    assert found["leads"][0]["saved"] is True and found["leads"][0]["recommended"] is False
    assert found["recommended"] == 0


def test_whatsapp_link_built_from_the_message_keeps_the_text_intact(app):
    app.vitrine()
    body = message(app).json()

    url = f"https://wa.me/{body['whatsapp']}?text=" + __import__("urllib.parse", fromlist=["quote"]).quote(body["text"])
    parts = urlsplit(url)

    assert parts.netloc == "wa.me" and parts.path == "/5511980150754"
    assert parse_qs(parts.query)["text"][0] == body["text"]
    assert unquote(parts.query.split("=", 1)[1]) == body["text"]


def test_leads_say_whether_their_follow_up_is_due(app):
    app.seed(lead("node-2", name="Recente", lat=-23.6, **CELULAR))
    contacted_days_ago(app, "node-1", "2026-11-05 15:00:00")
    contacted_days_ago(app, "node-2", "2026-11-06 15:00:00")

    flags = {item["id"]: item["follow_up_due"] for item in app.client.get("/api/leads").json()}

    assert flags == {"node-1": True, "node-2": False}


def test_the_update_response_carries_the_follow_up_flag_and_clears_it_after_sending(app):
    contacted_days_ago(app, "node-1", "2026-11-01 15:00:00")

    assert app.client.patch("/api/leads/node-1", json={"notes": "x"}).json()["follow_up_due"] is True
    assert app.client.patch("/api/leads/node-1", json={"follow_up_sent": True}).json()["follow_up_due"] is False
