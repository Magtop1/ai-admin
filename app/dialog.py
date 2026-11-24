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

    if p.service_id:
        state["service"] = p.service_id
    if p.qty:
        state["qty"] = p.qty
    if p.urgent:
        state["urgent"] = True

    service = next((s for s in niche.services if s.id == state.get("service")), None)

    # человек уже написал телефон: ловим заявку
    if p.phone:
        state["phone"] = p.phone
        attach_lead = True

    if p.intent == "greeting" and not service:
        return niche.greeting, None, state, attach_lead

    if p.intent == "human":
        return (
            "Передам администратору. Напишите телефон и удобное время, он ответит в течение 15 минут в рабочее время. "
            "Если вопрос простой, я тоже могу ответить сразу.",
            None,
            state,
            attach_lead,
        )

    if not service:
        tail = f" Если нужен расчёт, назовите услугу и объём. {_service_hint(niche)}"
        return ("Понял вопрос, но пока не вижу, о какой услуге речь." + tail), None, state, attach_lead

    q = pricing.quote(niche, service, state.get("qty"), bool(state.get("urgent")))
    quote_payload = _quote_payload(q)
    state["stage"] = "quoted"

    if service.per_unit and not state.get("qty"):
        text_lines = [
            f"{service.name}: {RUB(service.price)} {service.unit}.",
            "Скажите тираж, и я покажу цену с учётом скидки от объёма.",
            niche.price_note,
        ]
        return "\n".join(text_lines), quote_payload, state, attach_lead

    parts = [q.as_text()]

    if p.booking or p.intent == "booking":
        slots = _slots()
        parts.append("Свободное время: " + ", ".join(slots) + ".")
        parts.append("Напишите время и телефон, запишу. Или назовите другое время, проверю.")
    elif service.price == 0:
        parts.append("Записать вас? Напишите удобный день и телефон.")
    else:
        parts.append("Если подходит, оставьте телефон, передам администратору и зафиксирую цену.")
        if niche.unknown:
            parts.append(f"Чего я не знаю: {niche.unknown}. Это уточнит администратор, врать не буду.")

    if p.phone:
        parts.append(f"Телефон записал: {p.phone}. Администратор свяжется в рабочее время.")

    return "\n".join(parts), quote_payload, state, attach_lead
