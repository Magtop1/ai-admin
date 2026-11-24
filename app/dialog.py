"""Логика диалога бота: шаг за шагом, без нейросети и без интернета.

Каждый ответ собирается из трёх частей: что поняли, что посчитали,
что дальше. Если бот чего-то не знает, он это говорит прямо, а не выдумывает.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import catalog, pricing
from .catalog import Niche
from .nlu import Parsed, parse

RUB = lambda v: f"{v:,}".replace(",", " ") + " ₽"


def _slots(n: int = 3) -> list[str]:
    now = datetime.now()
    out, day = [], 0
    while len(out) < n:
        d = now + timedelta(days=day)
        if day == 0 and d.hour >= 18:
            day += 1
            continue
        if d.weekday() < 6:
            for hh, mm in (("10", "00"), ("14", "30"), ("18", "00")):
                if day > 0 or (d.hour, d.minute) < (int(hh), int(mm)):
                    out.append(f"{d.day:02d}.{d.month:02d} в {hh}:{mm}")
                if len(out) >= n:
                    break
        day += 1
    return out


def _service_hint(niche: Niche) -> str:
    names = ", ".join(s.name.lower() for s in niche.services[:3])
    return f"Уточните услугу: {names} и остальное из прайса."


def _quote_payload(q: pricing.Quote) -> dict:
    return {
        "service": q.service.name,
        "service_id": q.service.id,
        "qty": q.qty,
        "unit_price": q.unit_price,
        "total_min": q.total_min,
        "total_max": q.total_max,
        "urgent": q.urgent_fee > 0,
    }


def answer(niche: Niche, state: dict, text: str) -> tuple[str, dict | None, dict, bool]:
    """Возвращает (ответ, смета, новое состояние, сохранять ли заявку)."""
    p: Parsed = parse(text, niche)
    state = dict(state)
    attach_lead = False
    quote_payload = None

    if p.services:
        known = list(dict.fromkeys(list(state.get("services") or []) + p.services))
        state["services"] = known[:3]
        state["service"] = known[0]
    if p.qty:
        state["qty"] = p.qty
    if p.urgent:
        state["urgent"] = True

    ids = state.get("services") or ([state["service"]] if state.get("service") else [])
    services = [s for s in (next((x for x in niche.services if x.id == i), None) for i in ids) if s]

    # человек уже написал телефон: ловим заявку
    if p.phone:
        state["phone"] = p.phone
        attach_lead = True

    if p.intent == "human":
        return (
            "Передам администратору. Напишите телефон и удобное время, он ответит в течение 15 минут в рабочее время. "
            "Если вопрос простой, я тоже могу ответить сразу.",
            None,
            state,
            attach_lead,
        )

    if p.intent == "greeting" and not services:
        return niche.greeting, None, state, attach_lead

    if not services:
        tail = f" Если нужен расчёт, назовите услугу и объём. {_service_hint(niche)}"
        extra = " Если услуги нет в списке, оставьте телефон: администратор посмотрит и ответит."
        return ("Понял вопрос, но пока не вижу, о какой услуге речь." + tail + extra), None, state, attach_lead

    primary = services[0]

    if primary.per_unit and not state.get("qty"):
        quote_payload = None
        return (
            f"{primary.name}: {RUB(primary.price)} {primary.unit}.\n"
            "Скажите тираж, и я покажу цену с учётом скидки от объёма.\n" + niche.price_note
        ), quote_payload, state, attach_lead

    blocks, payload = [], None
    for svc in services[:2]:
        qty = state.get("qty") if svc.per_unit else None
        q = pricing.quote(niche, svc, qty, bool(state.get("urgent")))
        if payload is None:
            payload = _quote_payload(q)
        blocks.append(q.as_text(include_note=False))

    state["stage"] = "quoted"
    parts = ["\n\n".join(blocks)]
    if niche.price_note:
        parts.append(niche.price_note)

    if any(s.price == 0 for s in services[:2]) or (p.booking or p.intent == "booking"):
        slots = _slots()
        parts.append("Свободное время: " + ", ".join(slots) + ".")
        parts.append("Напишите время и телефон, запишу. Или назовите другое время, проверю.")
    else:
        parts.append("Если подходит, оставьте телефон, передам администратору и зафиксирую цену.")
        if niche.unknown:
            parts.append(f"Чего я не знаю: {niche.unknown}. Это уточнит администратор, врать не буду.")

    if p.phone:
        parts.append(f"Телефон записал: {p.phone}. Администратор свяжется в рабочее время.")

    return "\n".join(parts), payload, state, attach_lead
