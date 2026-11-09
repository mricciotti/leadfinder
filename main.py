import os
from contextlib import closing
from datetime import date
from uuid import uuid4
from pathlib import Path
from typing import Annotated, Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field, field_validator, model_validator

import contacts
import db
import export
import filters
import mensagens
import outreach
import overpass
import places
import scoring
import vitrines
import zones

INDEX = Path(__file__).parent / "static" / "index.html"
MAX_PREVIEWS = 10
RECOMMENDED_SITE_STATES = ("sem_site_na_fonte", "so_rede_social")


class SearchIn(BaseModel):
    segment: str
    zone: Literal[tuple(zones.ZONES)] | None = None
    neighborhood: str | None = None
    city: str = "São Paulo"

    @model_validator(mode="after")
    def needs_zone_or_neighborhood(self):
        if not self.zone and len((self.neighborhood or "").strip()) < 2:
            raise ValueError("Escolha uma zona ou informe um bairro.")
        return self


class LeadFilter(BaseModel):
    segment: str | None = None
    zone: Literal[tuple(zones.ZONES)] | None = None
    neighborhood: str | None = None
    city: str | None = None
    uf: str | None = None
    status: Literal[db.STATUSES] | None = None
    site: Literal[tuple(filters.SITE_FILTERS)] | None = None
    priority: Literal[scoring.PRIORITY_ORDER] | None = None
    offer: Literal[tuple(scoring.OFFERS)] | None = None
    phone: bool = False
    email: bool = False
    instagram: bool = False
    favorite: bool = False
    not_contacted: bool = False
    queue: Literal["hoje", "follow_up"] | None = None


class ServiceIn(BaseModel):
    name: str = Field(max_length=60)
    text: str = Field(default="", max_length=160)


class MenuItemIn(BaseModel):
    name: str = Field(max_length=60)
    price: str = Field(default="", max_length=20)


class VitrineIn(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=160)
    hours: str | None = Field(default=None, max_length=120)
    services: list[ServiceIn] | None = Field(default=None, max_length=8)
    menu: list[MenuItemIn] | None = Field(default=None, max_length=40)
    approved: bool | None = None


class SaveIn(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=5000)


def is_recommended(lead):
    return (
        not lead["saved"]
        and not lead["duplicate"]
        and lead["evaluation"]["contact"]["channel"]
        and lead["site_state"] in RECOMMENDED_SITE_STATES
    )


def build_preview(conn, leads):
    saved = db.statuses_of(conn, [lead["id"] for lead in leads])
    shown = []
    kept = []
    for lead in leads:
        known = lead["id"] in saved
        duplicate = not known and (
            db.same_place_elsewhere(conn, lead)
            or any(db.same_place(lead, other) for other in kept)
        )
        if not known and not duplicate:
            kept.append(lead)
        shown.append(
            {
                **lead,
                "manual_whatsapp": None,
                "saved": known,
                "saved_status": saved.get(lead["id"]),
                "duplicate": duplicate,
            }
        )
    ranked = scoring.ranked(shown)
    return [{**lead, "recommended": bool(is_recommended(lead))} for lead in ranked]


def checked_phone(value, kinds):
    if not value:
        return ""
    national, kind = contacts.normalize_phone(value)
    if kind not in kinds:
        raise ValueError("Telefone inválido. Inclua o DDD.")
    return national


class UpdateIn(BaseModel):
    status: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    favorite: bool | None = None
    absence_confirmed: bool | None = None
    manual_phone: str | None = Field(default=None, max_length=40)
    manual_whatsapp: str | None = Field(default=None, max_length=40)
    manual_instagram: str | None = Field(default=None, max_length=200)
    manual_website: str | None = Field(default=None, max_length=500)
    do_not_contact: bool | None = None
    follow_up_sent: bool | None = None

    @field_validator("status")
    @classmethod
    def status_must_exist(cls, value):
        if value is not None and value not in db.STATUSES:
            raise ValueError("Status inválido.")
        return value

    @field_validator("manual_phone")
    @classmethod
    def phone_must_have_ddd(cls, value):
        return checked_phone(value, ("celular", "fixo", "outro"))

    @field_validator("manual_whatsapp")
    @classmethod
    def whatsapp_must_have_ddd(cls, value):
        return checked_phone(value, ("celular", "fixo"))

    @field_validator("manual_instagram")
    @classmethod
    def instagram_must_be_a_profile(cls, value):
        if not value:
            return ""
        handle = contacts.normalize_instagram(value)
        if handle is None:
            raise ValueError("Instagram inválido. Use o @ ou o link do perfil.")
        return handle

    @field_validator("manual_website")
    @classmethod
    def website_must_be_own_site(cls, value):
        if not value:
            return ""
        url = contacts.normalize_url(value)
        if url is None:
            raise ValueError("Site inválido.")
        if contacts.classify_url(url) != "propria":
            raise ValueError("Isso não é um site próprio. Use o campo Instagram ou as anotações.")
        return url

    def changes(self):
        result = {}
        for key, value in self.model_dump(exclude_unset=True).items():
            if key in db.MANUAL_FIELDS:
                result[key] = value or None
            elif value is not None:
                result[key] = value
        return result


def clean_base(value):
    url = contacts.normalize_url(value) if value else None
    return url.rstrip("/") if url else None


def create_app(
    db_path,
    searcher=overpass.search,
    *,
    now=outreach.utc_now,
    vitrines_dir="vitrines_publicadas",
    clientes_dir="clientes",
    public_base=None,
):
    app = FastAPI()
    previews = {}
    base_url = clean_base(public_base)

    def filtered_leads(wanted):
        current = now()
        with closing(db.connect(db_path)) as conn:
            leads = db.list_leads(conn)
            slugs = db.vitrine_slug_by_lead(conn)
            remaining = outreach.today(conn, current)["remaining"]
        ranked = scoring.ranked(leads)
        for lead in ranked:
            lead["vitrine_slug"] = slugs.get(lead["id"])
            lead["follow_up_due"] = outreach.follow_up_due(lead, current)
        chosen = filters.apply(ranked, wanted.model_dump())
        if wanted.queue == "hoje":
            return outreach.daily_queue(chosen, remaining)
        if wanted.queue == "follow_up":
            return outreach.follow_ups(chosen, current)
        return chosen

    def vitrine_info(vitrine):
        return {
            "slug": vitrine["slug"],
            "approved": vitrine["approved"],
            "content": vitrine["content"],
            "created_at": vitrine["created_at"],
            "updated_at": vitrine["updated_at"],
            "exported_at": vitrine["exported_at"],
            "local_url": f"/s/{vitrine['slug']}",
            "public_url": f"{base_url}/{vitrine['slug']}/" if base_url else None,
        }

    def load_vitrine(conn, slug):
        vitrine = db.vitrine_by_slug(conn, slug)
        if vitrine is None:
            raise HTTPException(404, "Vitrine não encontrada.")
        return vitrine, db.get_lead(conn, vitrine["lead_id"])

    def refuse_blocked(lead):
        if lead["status"] == "descartado" or lead["do_not_contact_at"]:
            raise HTTPException(
                409, "Lead descartado ou marcado como não contatar não recebe vitrine."
            )

    @app.get("/")
    def index():
        return FileResponse(INDEX)

    @app.get("/api/segments")
    def segments():
        return [
            {"key": key, "label": label}
            for key, (label, _) in overpass.SEGMENTS.items()
        ]

    @app.get("/api/zones")
    def zone_list():
        return [{"key": key, "label": label} for key, (label, _) in zones.ZONES.items()]

    @app.get("/api/leads")
    def list_leads(wanted: Annotated[LeadFilter, Query()]):
        return filtered_leads(wanted)

    @app.get("/api/leads-table")
    def leads_table(wanted: Annotated[LeadFilter, Query()]):
        return export.table(filtered_leads(wanted))

    @app.get("/api/neighborhoods")
    def neighborhoods(city: str = places.CITY):
        return places.names(city)

    @app.get("/api/areas")
    def searched_areas():
        with closing(db.connect(db_path)) as conn:
            return filters.areas(scoring.ranked(db.list_leads(conn)))

    @app.get("/api/filter-options")
    def filter_options():
        with closing(db.connect(db_path)) as conn:
            return filters.options(db.list_leads(conn))

    @app.get("/api/export/{kind}")
    def export_leads(kind: Literal["leads", "completo"], wanted: Annotated[LeadFilter, Query()]):
        leads = filtered_leads(wanted)
        if not leads:
            raise HTTPException(404, "Nenhum lead para exportar com esses filtros.")
        content = export.leads_csv(leads) if kind == "leads" else export.full_csv(leads)
        name = export.file_name(kind, wanted.model_dump(), date.today())
        return Response(
            content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.post("/api/search")
    async def search(body: SearchIn):
        if body.segment not in overpass.SEGMENTS:
            raise HTTPException(400, "Segmento desconhecido.")
        if body.zone:
            neighborhood, city = zones.label(body.zone), zones.CITY
            extra = {"zone": body.zone}
        else:
            neighborhood, city = body.neighborhood.strip(), body.city.strip()
            known_place = places.find(neighborhood, city)
            extra = {"place": known_place} if known_place else {}
        try:
            result = await searcher(body.segment, neighborhood, city, **extra)
        except overpass.PlaceNotFound:
            raise HTTPException(
                404, "Não encontrei esse bairro. Confira o nome e a cidade."
            )
        except httpx.HTTPError:
            raise HTTPException(
                502,
                "O OpenStreetMap não respondeu, mesmo depois de algumas tentativas. Espere um minuto e tente de novo.",
            )
        with closing(db.connect(db_path)) as conn:
            shown = build_preview(conn, result["leads"])
        search_id = uuid4().hex
        previews[search_id] = {lead["id"]: lead for lead in result["leads"]}
        while len(previews) > MAX_PREVIEWS:
            del previews[next(iter(previews))]
        return {
            "search_id": search_id,
            "total": result["total"],
            "found": len(shown),
            "new": sum(not lead["saved"] and not lead["duplicate"] for lead in shown),
            "known": sum(lead["saved"] for lead in shown),
            "duplicates": sum(lead["duplicate"] for lead in shown),
            "without_site": sum(
                lead["site_state"] == "sem_site_na_fonte" for lead in shown
            ),
            "recommended": sum(lead["recommended"] for lead in shown),
            "leads": shown,
        }

    @app.post("/api/search/{search_id}/save")
    def save_search(search_id: str, body: SaveIn):
        found = previews.get(search_id)
        if found is None:
            raise HTTPException(404, "A prévia expirou. Faça a busca de novo.")
        if any(lead_id not in found for lead_id in body.ids):
            raise HTTPException(400, "Algum lead escolhido não faz parte desta busca.")
        with closing(db.connect(db_path)) as conn:
            saved = db.statuses_of(conn, list(found))
            chosen = [found[lead_id] for lead_id in dict.fromkeys(body.ids) if lead_id not in saved]
            refreshed = [lead for lead_id, lead in found.items() if lead_id in saved]
            added = db.add_leads(conn, chosen + refreshed)
        del previews[search_id]
        return {"added": added, "refreshed": len(refreshed)}

    @app.patch("/api/leads/{lead_id}")
    def update_lead(lead_id: str, body: UpdateIn):
        with closing(db.connect(db_path)) as conn:
            lead = db.update_lead(conn, lead_id, **body.changes())
            vitrine = db.vitrine_of_lead(conn, lead_id) if lead else None
        if lead is None:
            raise HTTPException(404, "Lead não encontrado.")
        return {
            **scoring.with_evaluation(lead),
            "vitrine_slug": vitrine["slug"] if vitrine else None,
            "follow_up_due": outreach.follow_up_due(lead, now()),
        }

    @app.get("/api/today")
    def today():
        with closing(db.connect(db_path)) as conn:
            return outreach.today(conn, now())

    @app.post("/api/leads/{lead_id}/vitrine")
    def create_vitrine(lead_id: str):
        with closing(db.connect(db_path)) as conn:
            lead = db.get_lead(conn, lead_id)
            if lead is None:
                raise HTTPException(404, "Lead não encontrado.")
            refuse_blocked(lead)
            vitrine = db.vitrine_of_lead(conn, lead_id)
            if vitrine is None:
                slug = vitrines.slug_for(lead, db.vitrine_slugs(conn))
                vitrine = db.create_vitrine(conn, lead_id, slug)
        return vitrine_info(vitrine)

    @app.get("/api/vitrines/{slug}")
    def get_vitrine(slug: str):
        with closing(db.connect(db_path)) as conn:
            vitrine, _ = load_vitrine(conn, slug)
        return vitrine_info(vitrine)

    @app.patch("/api/vitrines/{slug}")
    def update_vitrine(slug: str, body: VitrineIn):
        changes = body.model_dump(exclude_unset=True)
        approved = changes.pop("approved", None)
        with closing(db.connect(db_path)) as conn:
            vitrine, _ = load_vitrine(conn, slug)
            content = dict(vitrine["content"])
            for key, value in changes.items():
                cleaned = value.strip() if isinstance(value, str) else value
                if cleaned:
                    content[key] = cleaned
                else:
                    content.pop(key, None)
            vitrine = db.update_vitrine(
                conn, slug, content=content if changes else None, approved=approved
            )
        return vitrine_info(vitrine)

    @app.get("/s/{slug}")
    def vitrine_page(slug: str):
        with closing(db.connect(db_path)) as conn:
            vitrine, lead = load_vitrine(conn, slug)
        content = vitrines.content_for(lead, vitrine["content"])
        page = vitrines.render(content, preview=not vitrine["approved"])
        return HTMLResponse(
            page, headers={"X-Robots-Tag": "noindex, nofollow", "Cache-Control": "no-store"}
        )

    @app.post("/api/vitrines/{slug}/export")
    def export_vitrine(slug: str):
        with closing(db.connect(db_path)) as conn:
            vitrine, lead = load_vitrine(conn, slug)
            refuse_blocked(lead)
            base = Path(vitrines_dir).resolve()
            folder = (base / vitrine["slug"]).resolve()
            if base not in folder.parents:
                raise HTTPException(400, "Pasta de destino inválida.")
            folder.mkdir(parents=True, exist_ok=True)
            content = vitrines.content_for(lead, vitrine["content"])
            page = vitrines.render(content, preview=not vitrine["approved"])
            (folder / "index.html").write_bytes(page.encode("utf-8"))
            vitrine = db.mark_exported(conn, vitrine["slug"])
        return {**vitrine_info(vitrine), "path": str(folder / "index.html")}

    @app.post("/api/vitrines/{slug}/folder")
    def client_folder(slug: str):
        with closing(db.connect(db_path)) as conn:
            vitrine, lead = load_vitrine(conn, slug)
            refuse_blocked(lead)
            base = Path(clientes_dir).resolve()
            folder = (base / vitrine["slug"]).resolve()
            if base not in folder.parents:
                raise HTTPException(400, "Pasta de destino inválida.")
            content = vitrines.content_for(lead, vitrine["content"])
            files = vitrines.client_files(lead, vitrine, content)
        folder.mkdir(parents=True, exist_ok=True)
        created = []
        for name, text in files.items():
            target = folder / name
            if name == "dados.json" or not target.exists():
                target.write_bytes(text.encode("utf-8"))
                created.append(name)
        return {"path": str(folder), "written": created}

    @app.get("/api/leads/{lead_id}/message")
    def lead_message(lead_id: str, kind: Literal["abordagem", "follow_up"] = "abordagem"):
        with closing(db.connect(db_path)) as conn:
            lead = db.get_lead(conn, lead_id)
            vitrine = db.vitrine_of_lead(conn, lead_id) if lead else None
        if lead is None:
            raise HTTPException(404, "Lead não encontrado.")
        if lead["do_not_contact_at"]:
            raise HTTPException(409, "Lead marcado como não contatar.")
        whatsapp = vitrines.whatsapp_digits(lead)
        answer = {
            "whatsapp": whatsapp,
            "can_whatsapp": bool(whatsapp),
            "link": None,
            "link_ready": False,
            "exported": bool(vitrine and vitrine["exported_at"]),
            "case": None,
            "text": None,
            "warnings": [],
            "reason": None,
        }
        if vitrine is None:
            return {**answer, "reason": "Crie a vitrine antes de montar a mensagem."}
        if not base_url:
            return {**answer, "reason": "Defina LEADFINDER_VITRINE_BASE (a URL onde você publica as prévias) para gerar o link."}
        link = f"{base_url}/{vitrine['slug']}/"
        evaluation = scoring.evaluate(lead)
        case = "follow_up" if kind == "follow_up" else mensagens.case_for(evaluation["offers"])
        label = overpass.SEGMENTS.get(lead["segment"], (lead["segment"],))[0]
        built = mensagens.build(case, lead, link, label)
        return {**answer, **built, "link": link, "link_ready": True}

    return app


app = create_app(
    os.environ.get("LEADFINDER_DB", "leads.db"),
    vitrines_dir=os.environ.get("LEADFINDER_VITRINES_DIR", "vitrines_publicadas"),
    clientes_dir=os.environ.get("LEADFINDER_CLIENTES_DIR", "clientes"),
    public_base=os.environ.get("LEADFINDER_VITRINE_BASE"),
)
