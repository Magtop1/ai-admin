"""Сайт-портфолио с четырьмя рабочими демо ИИ-администратора.

Запуск:  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import catalog, dialog, storage

BASE = Path(__file__).resolve().parent
app = FastAPI(title="ИИ-администратор: портфолио и живые демо", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))

BRAND = {
    "author": "Алексей",
    "telegram": "@hello_nastra",
    "phone": "+7 986 925-07-48",
    "mail": "magtope12@gmail.com",
}


@app.get("/health")
def health() -> dict:
    return {"ok": True, "niches": len(catalog.NICHES)}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    con = storage.connect()
    s = storage.stats(con)
    return templates.TemplateResponse(
        request, "index.html",
        {"niches": catalog.NICHES, "brand": BRAND, "stats": s},
    )


@app.get("/demo/{slug}", response_class=HTMLResponse)
def demo(request: Request, slug: str):
    niche = catalog.get(slug)
    if not niche:
        return HTMLResponse("<h1>Нет такого демо</h1>", status_code=404)
    return templates.TemplateResponse(
        request, "demo.html",
        {"n": niche, "brand": BRAND, "niches": catalog.NICHES},
    )


class Msg(BaseModel):
    slug: str
    session_id: str
    text: str


@app.post("/api/chat")
def chat(msg: Msg):
    niche = catalog.get(msg.slug)
    if not niche:
        return JSONResponse({"error": "unknown niche"}, status_code=404)
    text = (msg.text or "").strip()[:500]
    if not text:
        return JSONResponse({"error": "empty text"}, status_code=422)

    con = storage.connect()
    state = storage.get_session(con, msg.session_id, niche.slug)
    storage.log_message(con, msg.session_id, "user", text)

    reply, quote, new_state, make_lead = dialog.answer(niche, state, text)
    storage.save_session(con, msg.session_id, new_state)
    storage.log_message(con, msg.session_id, "bot", reply)

    lead_id = None
    if make_lead and new_state.get("phone"):
        lead_id = storage.add_lead(con, msg.session_id, niche.slug, new_state.get("name"),
                                   new_state.get("phone"), text, quote)

    return {"reply": reply, "quote": quote, "lead_id": lead_id,
            "state": {k: new_state.get(k) for k in ("service", "qty", "urgent", "phone")}}


@app.get("/api/leads")
def api_leads(niche: str | None = None):
    return {"leads": storage.leads(storage.connect(), niche)}


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    con = storage.connect()
    return templates.TemplateResponse(
        request, "admin.html",
        {"rows": storage.leads(con), "stats": storage.stats(con), "niches": catalog.NICHES, "brand": BRAND},
    )


@app.get("/admin.csv")
def admin_csv():
    data = storage.leads_csv(storage.connect())
    return Response(content=data, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="leads.csv"'})


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    return "User-agent: *\nDisallow: /admin\n"
