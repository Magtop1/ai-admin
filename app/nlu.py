"""Разбор живого текста клиента без нейросетей и без интернета.

Задача узкая и проверяемая: понять услугу, тираж, срочность, намерение
и снять с текста телефон, если человек его уже написал.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .catalog import Niche, find_service, hits

NUM_WORDS = {
    "один": 1, "одну": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5,
    "десять": 10, "сто": 100, "двести": 200, "триста": 300, "пятьсот": 500,
    "тысяча": 1000, "тысячу": 1000, "тысячи": 1000, "полторы": 1500,
}
URGENT = ("срочно", "срочн", "к утру", "сегодня", "прямо сейчас", "как можно быстрее", "горит", "асап")
BOOKING = ("запиш", "запись", "записаться", "можно на", "свободно", "окно", "когда можно", "примите")
HUMAN = ("человек", "менеджер", "администратор", "позовите", "живой", "перезвон")
PHONE_RE = re.compile(r"(?:\+7|8|7)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
QTY_RE = re.compile(r"(\d[\d\s]{0,7})\s*(тыс|тысяч|шт|штук|лист|экз|копи|руб)?", re.I)


@dataclass
class Parsed:
    intent: str
    service_id: str | None = None
    qty: int | None = None
    urgent: bool = False
    phone: str | None = None
    booking: bool = False
    raw: str = ""
    tags: list[str] = field(default_factory=list)


def _qty(text: str) -> int | None:
    # телефон это не тираж: цифры из номера выкидываем до разбора
    low = PHONE_RE.sub(" ", text.lower().replace("ё", "е"))
    m = QTY_RE.search(low)
    if m:
        num = int(re.sub(r"\D", "", m.group(1)) or 0)
        if num:
            unit = (m.group(2) or "").lower()
            if unit.startswith(("тыс", "шт", "штук", "экз", "лист", "копи")) and num < 100:
                # "5 тыс" это 5000, а "5 штук" так и остаётся пятёркой
                return num * 1000 if unit.startswith("тыс") else num
            return num
    for word, val in NUM_WORDS.items():
        if hits(word, low):
            return val
    return None


def parse(text: str, niche: Niche) -> Parsed:
    low = (text or "").lower().replace("ё", "е")
    p = Parsed(intent="smalltalk", raw=text)

    if any(k in low for k in HUMAN):
        p.intent = "human"
        p.tags.append("human")

    phone = PHONE_RE.search(low)
    if phone:
        digits = re.sub(r"\D", "", phone.group(0))
        if len(digits) == 11:
            p.phone = "+7 " + f"{digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
            p.tags.append("phone")

    if any(k in low for k in URGENT):
        p.urgent = True
        p.tags.append("urgent")
    if any(k in low for k in BOOKING):
        p.booking = True
        p.tags.append("booking")

    svc = find_service(niche, low)
    if svc:
        p.service_id = svc.id
        p.tags.append("service:" + svc.id)

    qty = _qty(low)
    if qty:
        p.qty = qty
        p.tags.append(f"qty:{qty}")

    price_words = ("сколько", "цена", "стоит", "стоимость", "прайс", "почем", "почём", "расчет", "расчёт", "смет")
    if p.service_id and (any(k in low for k in price_words) or p.qty):
        p.intent = "price"
    elif p.service_id and p.booking:
        p.intent = "booking"
    elif p.service_id:
        p.intent = "price"
    elif p.phone:
        p.intent = "contact"
    elif any(k in low for k in ("привет", "здравств", "добрый", "доброе")):
        p.intent = "greeting"
    return p
