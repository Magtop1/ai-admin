"""Сверка статической версии с серверной.

Статика считает в JS, сервер в Python. Если правила разойдутся, клиент увидит
одну цену в демо на сайте и другую в боте у себя. Этот тест ловит расхождение
на матрице случаев: все услуги, все тиражи, обычный и срочный заказ.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app import catalog, pricing

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "app" / "static" / "engine.js"
NODE = shutil.which("node")

CASES: list[tuple[str, str, int | None, bool]] = []
for slug, niche in catalog.NICHES.items():
    for svc in niche.services:
        qtys = [None, 100, 250, 500, 1000, 3000, 5000, 10000] if svc.per_unit else [None]
        for q in qtys:
            for urgent in (False, True):
                CASES.append((slug, svc.id, q, urgent))


def python_result(slug: str, service_id: str, qty: int | None, urgent: bool) -> dict:
    niche = catalog.NICHES[slug]
    svc = next(s for s in niche.services if s.id == service_id)
    q = pricing.quote(niche, svc, qty if svc.per_unit else None, urgent)
    return {
        "unit_price": q.unit_price,
        "subtotal": q.subtotal,
        "urgent_fee": q.urgent_fee,
        "delivery": q.delivery,
        "total_min": q.total_min,
        "total_max": q.total_max,
        "tier_k": round(q.tier_k, 6),
        "per_label": q.price_per_label(),
    }


@pytest.mark.skipif(NODE is None, reason="node не установлен")
def test_js_matches_python():
    payload = {
        "catalog": {
            slug: {
                "slug": n.slug, "unit_tiers": {str(k): v for k, v in n.unit_tiers.items()},
                "urgent_k": n.urgent_k, "delivery": n.delivery, "price_note": n.price_note,
                "services": [
                    {"id": s.id, "name": s.name, "price": s.price, "unit": s.unit,
                     "keywords": list(s.keywords), "per_unit": s.per_unit} for s in n.services
                ],
            } for slug, n in catalog.NICHES.items()
        },
        "cases": [{"slug": s, "service": sid, "qty": q, "urgent": u} for s, sid, q, u in CASES],
    }
    script = """
    const fs = require('fs');
    require(process.argv[1]);
    const data = JSON.parse(fs.readFileSync(0, 'utf8'));
    const Bot = globalThis.Bot;
    const out = data.cases.map(c => {
      const niche = data.catalog[c.slug];
      const svc = niche.services.filter(s => s.id === c.service)[0];
      const q = Bot.quote(niche, svc, svc.per_unit ? c.qty : null, c.urgent);
      return {
        unit_price: q.unit_price, subtotal: q.subtotal, urgent_fee: q.urgent_fee,
        delivery: q.delivery, total_min: q.total_min, total_max: q.total_max,
        tier_k: Math.round(q.tier_k * 1e6) / 1e6, per_label: Bot.pricePerLabel(q)
      };
    });
    process.stdout.write(JSON.stringify(out));
    """
    # загрузка движка: window нет, engine.js кладёт Bot в globalThis
    proc = subprocess.run(
        [NODE, "-e", script, str(ENGINE)],
        input=json.dumps(payload), capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    js_rows = json.loads(proc.stdout)
    assert len(js_rows) == len(CASES)

    bad = []
    for (slug, sid, qty, urgent), js in zip(CASES, js_rows):
        py = python_result(slug, sid, qty, urgent)
        if py != js:
            bad.append((slug, sid, qty, urgent, py, js))
    assert not bad, f"расхождений {len(bad)}, первое: {bad[0]}"


@pytest.mark.skipif(NODE is None, reason="node не установлен")
def test_js_parses_same_services():
    payload = {"catalog": {slug: {"services": [
        {"id": s.id, "keywords": list(s.keywords)} for s in n.services]} for slug, n in catalog.NICHES.items()},
        "texts": ["визитки 5000 срочно", "сколько стоит имплант", "есть пробное и сколько стоит месяц",
                  "болит зуб, +7 986 925-07-48", "спасибо, а бассейн входит?", "хочу на чистку в субботу"]}
    script = """
    const fs = require('fs');
    require(process.argv[1]);
    const data = JSON.parse(fs.readFileSync(0, 'utf8'));
    const out = {};
    data.texts.forEach(t => {
      out[t] = {};
      Object.keys(data.catalog).forEach(slug => {
        const niche = data.catalog[slug];
        niche.services = niche.services.map(s => Object.assign({price: 100, unit: 'за штуку'}, s));
        niche.greeting = ''; niche.price_note = ''; niche.unit_tiers = {}; niche.urgent_k = 1; niche.delivery = 0;
        const p = globalThis.Bot.parse(t, niche);
        out[t][slug] = [p.intent, p.service_id, p.qty, p.urgent, p.phone];
      });
    });
    process.stdout.write(JSON.stringify(out));
    """
    proc = subprocess.run([NODE, "-e", script, str(ENGINE)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    js = json.loads(proc.stdout)

    from app.nlu import parse
    for text, per_niche in js.items():
        for slug, got in per_niche.items():
            p = parse(text, catalog.NICHES[slug])
            assert got == [p.intent, p.service_id, p.qty, p.urgent, p.phone], (text, slug, got)
