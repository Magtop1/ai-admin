"""Расчёт сметы. Один и тот же код считает и бот, и тесты.

Правила:
- цена берётся из прайса, ничего не выдумываем;
- для тиражных услуг работает скидка от объёма;
- срочность это множитель из настроек ниши;
- если услуга "от", клиент видит вилку, а не одну цифру.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .catalog import Niche, Service


@dataclass
class Quote:
    service: Service
    qty: int | None
    unit_price: int
    subtotal: int
    tier_k: float
    urgent_k: float
    urgent_fee: int
    delivery: int
    total_min: int
    total_max: int
    lines: list[str] = field(default_factory=list)
    note: str = ""

    def price_per_label(self) -> int:
        """Цена в тех же единицах, в которых она указана в прайсе."""
        if self.service.per_unit and self.qty:
            return round(self.subtotal * 1000 / self.qty) if "1000" in self.service.unit else round(self.subtotal / self.qty)
        return self.service.price

    def as_text(self, include_note: bool = True) -> str:
        rub = lambda v: f"{v:,}".replace(",", " ") + " ₽"
        if self.service.price == 0:
            out = [f"{self.service.name}: бесплатно"]
        else:
            out = [f"{self.service.name}: {rub(self.price_per_label())} {self.service.unit}"]
        if self.qty and self.service.per_unit:
            if self.tier_k < 1:
                out.append(f"Тираж: {self.qty} шт, скидка от объёма {round((1 - self.tier_k) * 100)}%")
            elif self.tier_k > 1:
                out.append(f"Тираж: {self.qty} шт, мелкий тираж дороже на {round((self.tier_k - 1) * 100)}%")
            else:
                out.append(f"Тираж: {self.qty} шт")
            out.append(f"Работа: {rub(self.subtotal)}")
        if self.urgent_fee:
            out.append(f"Срочность: {rub(self.urgent_fee)}")
        if self.delivery:
            out.append(f"Доставка по Москве: {rub(self.delivery)}")
        if self.total_max == 0:
            out.append("Итого: бесплатно")
        elif self.total_max > self.total_min:
            out.append(f"Итого: от {rub(self.total_min)} до {rub(self.total_max)}")
        else:
            out.append(f"Итого: {rub(self.total_min)}")
        if include_note and self.note:
            out.append(self.note)
        return "\n".join(out)


def tier_for(service: Service, qty: int, niche: Niche) -> float:
    if not service.per_unit or not niche.unit_tiers:
        return 1.0
    best = 1.0
    for edge in sorted(niche.unit_tiers):
        if qty >= edge:
            best = niche.unit_tiers[edge]
    return best


def quote(niche: Niche, service: Service, qty: int | None = None, urgent: bool = False) -> Quote:
    k = tier_for(service, qty or 0, niche)
    if qty and service.per_unit:
        # базовая цена указана за 1000 штук или за лист, приводим к тиражу
        base_for_1000 = service.price / 1000 if service.price > 50 else service.price
        unit = max(1, round(base_for_1000 * k))
        subtotal = unit * qty
        if service.price > 50:
            subtotal = round(service.price * k * qty / 1000)
            unit = max(1, round(subtotal / qty))
    else:
        unit = service.price
        subtotal = service.price

    urgent_fee = round(subtotal * (niche.urgent_k - 1)) if urgent and niche.urgent_k > 1 else 0
    # доставка не отменяется срочностью: срочно не значит бесплатно привезти
    delivery = niche.delivery
    total = subtotal + urgent_fee + delivery

    if service.price == 0:
        lo = hi = 0
    elif service.per_unit:
        lo, hi = total, round(total * 1.08)
    else:
        lo, hi = total, round(total * 1.35)

    return Quote(
        service=service, qty=qty, unit_price=unit, subtotal=subtotal, tier_k=k,
        urgent_k=niche.urgent_k if urgent else 1.0, urgent_fee=urgent_fee, delivery=delivery,
        total_min=lo, total_max=hi, note=niche.price_note,
    )
