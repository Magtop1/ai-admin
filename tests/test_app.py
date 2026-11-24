"""Тесты правил: разбор вопросов, расчёт сметы, API и база заявок."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import catalog, dialog, pricing, storage
from app.main import app
from app.nlu import parse

TYPO = catalog.NICHES["typography"]
AUTO = catalog.NICHES["avtoservis"]
DENT = catalog.NICHES["stomatology"]


def test_catalog_has_four_niches():
    assert len(catalog.NICHES) == 4
    for n in catalog.NICHES.values():
        assert n.services, n.slug
        assert n.greeting
        assert n.price_note


@pytest.mark.parametrize("text,service,qty", [
    ("визитки 1000 штук", "cards", 1000),
    ("нужны листовки, 5 тыс", "leaflets", 5000),
    ("буклеты 500", "booklets", 500),
    ("баннер 1х2 м", "banner", None),
    ("сколько стоит тиражирование документов", "copy", None),
])
def test_parse_typography(text, service, qty):
    p = parse(text, TYPO)
    assert p.service_id == service
    if qty:
        assert p.qty == qty


def test_urgency_and_phone():
    p = parse("срочно визитки 1000, телефон +7 986 925-07-48", TYPO)
    assert p.urgent and p.phone == "+7 986 925-07-48"


def test_price_intent_and_human():
    assert parse("сколько стоит имплант", DENT).intent == "price"
    assert parse("позовите живого менеджера", AUTO).intent == "human"


def test_tier_discount_grows_with_qty():
    svc = next(s for s in TYPO.services if s.id == "cards")
    small = pricing.quote(TYPO, svc, 500)
    big = pricing.quote(TYPO, svc, 5000)
    assert big.tier_k < small.tier_k
    assert big.total_min / 5000 < small.total_min / 500


def test_urgent_is_more_expensive():
    svc = next(s for s in TYPO.services if s.id == "leaflets")
    calm = pricing.quote(TYPO, svc, 1000, urgent=False)
    fast = pricing.quote(TYPO, svc, 1000, urgent=True)
    assert fast.total_min > calm.total_min
    assert fast.urgent_fee == round(calm.subtotal * (TYPO.urgent_k - 1))


def test_service_price_is_range_not_single_number():
    svc = next(s for s in AUTO.services if s.id == "oil")
    q = pricing.quote(AUTO, svc)
    assert q.total_max > q.total_min
    assert "от" in q.as_text()


def test_free_service_stays_free():
    svc = next(s for s in DENT.services if s.id == "consult")
    q = pricing.quote(DENT, svc)
    assert q.total_min == 0 and q.total_max == 0


def test_dialog_asks_qty_before_quote():
    text, quote, state, lead = dialog.answer(TYPO, {}, "сколько стоят визитки")
    assert "тираж" in text.lower()
    assert quote is None  # без тиража смету не называем
    assert state["service"] == "cards"
    assert lead is False


def test_two_services_in_one_question():
    text, quote, state, _ = dialog.answer(catalog.NICHES["fitness"], {}, "есть пробное и сколько стоит месяц")
    assert "Пробное занятие" in text and "Месяц без ограничений" in text
    assert quote["service_id"] in ("trial", "month")


def test_dialog_quotes_when_qty_known():
    text, quote, state, lead = dialog.answer(TYPO, {"service": "cards", "qty": None}, "визитки 1000")
    assert "Итого" in text
    assert quote["qty"] == 1000
    assert lead is False


def test_dialog_catches_lead_on_phone():
    text, quote, state, lead = dialog.answer(AUTO, {"service": "oil"}, "замена масла, +7 986 925-07-48")
    assert lead is True
    assert state["phone"] == "+7 986 925-07-48"


def test_no_dashes_in_any_ui_text():
    bad = re.compile("[\u2014\u2013]")
    root = Path(__file__).resolve().parent.parent
    for path in list(root.glob("app/**/*.py")) + list(root.glob("app/**/*.html")) + list(root.glob("app/**/*.js")):
        assert not bad.search(path.read_text(encoding="utf-8")), path


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr(storage, "DB_PATH", db)
    return TestClient(app)


def test_pages_render(client):
    for url in ("/", "/demo/typography", "/demo/avtoservis", "/demo/stomatology", "/demo/fitness", "/admin", "/health"):
        r = client.get(url)
        assert r.status_code == 200, url


def test_chat_creates_lead(client):
    sid = "test-session-1"
    r1 = client.post("/api/chat", json={"slug": "typography", "session_id": sid, "text": "визитки 1000"})
    assert r1.status_code == 200
    data = r1.json()
    assert "Итого" in data["reply"]
    assert data["quote"]["qty"] == 1000
    assert data["lead_id"] is None

    r2 = client.post("/api/chat", json={"slug": "typography", "session_id": sid, "text": "беру, +7 986 925-07-48"})
    assert r2.json()["lead_id"] is not None

    rows = client.get("/api/leads?niche=typography").json()["leads"]
    assert rows and rows[0]["phone"] == "+7 986 925-07-48"

    csv_text = client.get("/admin.csv").text
    assert "986" in csv_text
