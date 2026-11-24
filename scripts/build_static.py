"""Сборка статической версии сайта для GitHub Pages.

Что делает:
  1. выгружает каталог прайсов из app/catalog.py в assets/catalog.json;
  2. рендерит страницы портфолио, четырёх демо и админки через Jinja2;
  3. копирует движок, клиентский скрипт, стили и .nojekyll;
  4. проверяет, что в готовых файлах нет длинных тире.

Запуск:  python3 scripts/build_static.py
Результат: static_site/
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import catalog  # noqa: E402

TPL = ROOT / "scripts" / "templates"
OUT = ROOT / "static_site"
BRAND = {
    "author": "Алексей",
    "telegram": "@hello_nastra",
    "phone": "+7 986 925-07-48",
    "mail": "magtope12@gmail.com",
}


def catalog_payload() -> dict:
    return {
        slug: {
            "slug": n.slug,
            "title": n.title,
            "short": n.short,
            "brand": n.brand,
            "tagline": n.tagline,
            "greeting": n.greeting,
            "price_note": n.price_note,
            "unknown": n.unknown,
            "urgent_k": n.urgent_k,
            "delivery": n.delivery,
            "unit_tiers": {str(k): v for k, v in n.unit_tiers.items()},
            "price_rub": n.price_rub,
            "retainer_rub": n.retainer_rub,
            "services": [
                {"id": s.id, "name": s.name, "price": s.price, "unit": s.unit,
                 "keywords": list(s.keywords), "per_unit": s.per_unit}
                for s in n.services
            ],
        }
        for slug, n in catalog.NICHES.items()
    }


def rub(v: int) -> str:
    return f"{v:,}".replace(",", " ") + " ₽"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    (OUT / "demo").mkdir()

    env = Environment(loader=FileSystemLoader(str(TPL)), autoescape=select_autoescape(["html"]))
    env.filters["rub"] = rub
    niches = catalog.NICHES

    (OUT / "index.html").write_text(
        env.get_template("portfolio.html").render(niches=niches, brand=BRAND), encoding="utf-8")
    (OUT / "admin.html").write_text(
        env.get_template("admin.html").render(brand=BRAND), encoding="utf-8")
    for slug, n in niches.items():
        (OUT / "demo" / f"{slug}.html").write_text(
            env.get_template("demo.html").render(n=n, brand=BRAND), encoding="utf-8")

    (OUT / "assets" / "catalog.json").write_text(
        json.dumps(catalog_payload(), ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy(ROOT / "app" / "static" / "engine.js", OUT / "assets" / "engine.js")
    shutil.copy(TPL / "client.js", OUT / "assets" / "client.js")
    shutil.copy(TPL / "admin.js", OUT / "assets" / "admin.js")
    shutil.copy(TPL / "site.css", OUT / "assets" / "site.css")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "404.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Страница не найдена</title>'
        '<p style="font:16px system-ui;padding:24px">Страницы нет. <a href="/">Вернуться на главную</a>.',
        encoding="utf-8")

    # самопроверка: без длинных тире и с живым движком
    bad = []
    for path in OUT.rglob("*"):
        if path.suffix in (".html", ".js", ".css", ".json"):
            text = path.read_text(encoding="utf-8")
            if "\u2014" in text or "\u2013" in text:
                bad.append(path.name)
    files = sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file())
    print(f"готово: {len(files)} файлов в {OUT.relative_to(ROOT)}/")
    for f in files:
        print("  ", f)
    if bad:
        raise SystemExit(f"найдены тире в: {bad}")
    print("проверка: длинных тире нет")


if __name__ == "__main__":
    main()
