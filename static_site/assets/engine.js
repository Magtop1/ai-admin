/* Движок бота для статической версии: те же правила, что в Python.
 *
 * Работает без сервера, без сети и без сборки. Каталог прайсов приходит
 * из catalog.json, который собирается из app/catalog.py, чтобы цены правились
 * в одном месте. Совпадение расчётов с Python проверяется тестом tests/test_parity.py.
 */
(function (root) {
  "use strict";

  var NUM_WORDS = {
    "один": 1, "одну": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5,
    "десять": 10, "сто": 100, "двести": 200, "триста": 300, "пятьсот": 500,
    "тысяча": 1000, "тысячу": 1000, "тысячи": 1000, "полторы": 1500
  };
  var URGENT = ["срочно", "срочн", "к утру", "сегодня", "прямо сейчас", "как можно быстрее", "горит", "асап"];
  var BOOKING = ["запиш", "запись", "записаться", "можно на", "свободно", "окно", "когда можно", "примите"];
  var HUMAN = ["человек", "менеджер", "администратор", "позовите", "живой", "перезвон"];
  var PRICE_WORDS = ["сколько", "цена", "стоит", "стоимость", "прайс", "почем", "расчет", "расчёт", "смет"];
  var QTY_RE = /(\d[\d\s]{0,7})\s*(тыс|тысяч|шт|штук|лист|экз|копи|руб)?/i;
  var PHONE_RE = /(?:\+7|8|7)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}/;

  function r(x) { return Math.floor(x + 0.5); }
  function norm(s) { return (s || "").toLowerCase().replace(/ё/g, "е"); }
  function isWord(ch) { return /[а-яa-z0-9]/.test(ch); }

  /* Ключ должен начинать слово: иначе "сто" поймается внутри "стоит".
     Для коротких ключей нужна ещё и граница справа. Без lookbehind,
     потому что старые Safari его не понимают. */
  function hits(key, low) {
    key = key.replace(/ё/g, "е");
    var from = 0, idx;
    while ((idx = low.indexOf(key, from)) !== -1) {
      var before = idx === 0 ? "" : low[idx - 1];
      var after = idx + key.length >= low.length ? "" : low[idx + key.length];
      var leftOk = before === "" || !isWord(before);
      var rightOk = key.length >= 4 || after === "" || !isWord(after);
      if (leftOk && rightOk) return true;
      from = idx + 1;
    }
    return false;
  }

  function qty_of(text) {
    var low = norm(text).replace(PHONE_RE, " ");
    var m = QTY_RE.exec(low);
    if (m) {
      var num = parseInt((m[1] || "").replace(/\D/g, ""), 10) || 0;
      if (num) {
        var unit = (m[2] || "").toLowerCase();
        if (/^(тыс|шт|штук|экз|лист|копи)/.test(unit) && num < 100) {
          return /^тыс/.test(unit) ? num * 1000 : num;
        }
        return num;
      }
    }
    for (var w in NUM_WORDS) {
      if (hits(w, low)) return NUM_WORDS[w];
    }
    return null;
  }

  function findServices(niche, low) {
    var scored = {};
    niche.services.forEach(function (s) {
      s.keywords.forEach(function (kw) {
        if (hits(kw, low)) {
          scored[s.id] = Math.max(scored[s.id] || 0, kw.length);
        }
      });
    });
    return Object.keys(scored)
      .sort(function (a, b) { return scored[b] - scored[a]; })
      .map(function (id) { return niche.services.filter(function (s) { return s.id === id; })[0]; });
  }

  function parse(text, niche) {
    var low = norm(text);
    var p = { intent: "smalltalk", service_id: null, services: [], qty: null, urgent: false, phone: null, booking: false, tags: [] };

    HUMAN.forEach(function (k) { if (low.indexOf(k) !== -1) { p.intent = "human"; p.tags.push("human"); } });

    var ph = PHONE_RE.exec(low);
    if (ph) {
      var digits = ph[0].replace(/\D/g, "");
      if (digits.length === 11) {
        p.phone = "+7 " + digits.slice(1, 4) + " " + digits.slice(4, 7) + "-" + digits.slice(7, 9) + "-" + digits.slice(9, 11);
        p.tags.push("phone");
      }
    }
    URGENT.forEach(function (k) { if (low.indexOf(k) !== -1) { p.urgent = true; p.tags.push("urgent"); } });
    BOOKING.forEach(function (k) { if (low.indexOf(k) !== -1) { p.booking = true; p.tags.push("booking"); } });

    var found = findServices(niche, low);
    if (found.length) {
      p.services = found.map(function (s) { return s.id; });
      p.service_id = found[0].id;
      found.forEach(function (s) { p.tags.push("service:" + s.id); });
    }

    var q = qty_of(low);
    if (q) { p.qty = q; p.tags.push("qty:" + q); }

    var wantsPrice = PRICE_WORDS.some(function (k) { return low.indexOf(k) !== -1; });
    if (p.service_id && (wantsPrice || p.qty)) p.intent = "price";
    else if (p.service_id && p.booking) p.intent = "booking";
    else if (p.service_id) p.intent = "price";
    else if (p.phone) p.intent = "contact";
    else if (["привет", "здравств", "добрый", "доброе"].some(function (k) { return low.indexOf(k) !== -1; })) p.intent = "greeting";
    return p;
  }

  function tierFor(service, qty, niche) {
    if (!service.per_unit || !niche.unit_tiers) return 1.0;
    var best = 1.0;
    Object.keys(niche.unit_tiers).map(Number).sort(function (a, b) { return a - b; }).forEach(function (edge) {
      if (qty >= edge) best = niche.unit_tiers[edge];
    });
    return best;
  }

  function rub(v) { return v.toLocaleString("ru-RU") + " ₽"; }

  function quote(niche, service, qty, urgent) {
    var k = tierFor(service, qty || 0, niche);
    var unit, subtotal;
    if (qty && service.per_unit) {
      var baseFor1000 = service.price > 50 ? service.price / 1000 : service.price;
      unit = Math.max(1, r(baseFor1000 * k));
      subtotal = unit * qty;
      if (service.price > 50) {
        subtotal = r(service.price * k * qty / 1000);
        unit = Math.max(1, r(subtotal / qty));
      }
    } else {
      unit = service.price;
      subtotal = service.price;
    }
    var urgentFee = urgent && niche.urgent_k > 1 ? r(subtotal * (niche.urgent_k - 1)) : 0;
    var delivery = niche.delivery || 0;
    var total = subtotal + urgentFee + delivery;
    var lo, hi;
    if (service.price === 0) { lo = hi = 0; }
    else if (service.per_unit) { lo = total; hi = r(total * 1.08); }
    else { lo = total; hi = r(total * 1.35); }
    return {
      service: service, qty: qty, unit_price: unit, subtotal: subtotal, tier_k: k,
      urgent_k: urgent ? niche.urgent_k : 1.0, urgent_fee: urgentFee, delivery: delivery,
      total_min: lo, total_max: hi
    };
  }

  function pricePerLabel(q) {
    if (q.service.per_unit && q.qty) {
      return q.service.unit.indexOf("1000") !== -1 ? r(q.subtotal * 1000 / q.qty) : r(q.subtotal / q.qty);
    }
    return q.service.price;
  }

  function quoteText(q, includeNote) {
    var out = [];
    if (q.service.price === 0) out.push(q.service.name + ": бесплатно");
    else out.push(q.service.name + ": " + rub(pricePerLabel(q)) + " " + q.service.unit);

    if (q.qty && q.service.per_unit) {
      if (q.tier_k < 1) out.push("Тираж: " + q.qty + " шт, скидка от объёма " + r((1 - q.tier_k) * 100) + "%");
      else if (q.tier_k > 1) out.push("Тираж: " + q.qty + " шт, мелкий тираж дороже на " + r((q.tier_k - 1) * 100) + "%");
      else out.push("Тираж: " + q.qty + " шт");
      out.push("Работа: " + rub(q.subtotal));
    }
    if (q.urgent_fee) out.push("Срочность: " + rub(q.urgent_fee));
    if (q.delivery) out.push("Доставка по Москве: " + rub(q.delivery));
    if (q.total_max === 0) out.push("Итого: бесплатно");
    else if (q.total_max > q.total_min) out.push("Итого: от " + rub(q.total_min) + " до " + rub(q.total_max));
    else out.push("Итого: " + rub(q.total_min));
    if (includeNote && q.note) out.push(q.note);
    return out.join("\n");
  }

  function slots(n) {
    n = n || 3;
    var out = [], day = 0, now = new Date();
    while (out.length < n && day < 30) {
      var d = new Date(now.getTime() + day * 86400000);
      if (!(day === 0 && d.getHours() >= 18) && d.getDay() !== 0) {
        [["10", "00"], ["14", "30"], ["18", "00"]].forEach(function (hm) {
          if (out.length < n && (day > 0 || (d.getHours() < +hm[0] || (d.getHours() === +hm[0] && d.getMinutes() < +hm[1])))) {
            out.push(("0" + d.getDate()).slice(-2) + "." + ("0" + (d.getMonth() + 1)).slice(-2) + " в " + hm[0] + ":" + hm[1]);
          }
        });
      }
      day++;
    }
    return out;
  }

  function hint(niche) {
    return "Уточните услугу: " + niche.services.slice(0, 3).map(function (s) { return s.name.toLowerCase(); }).join(", ") + " и остальное из прайса.";
  }

  function answer(niche, state, text) {
    var p = parse(text, niche);
    state = Object.assign({}, state);
    var attachLead = false, payload = null;

    if (p.services.length) {
      var known = (state.services || []).concat(p.services).filter(function (v, i, a) { return a.indexOf(v) === i; });
      state.services = known.slice(0, 3);
      state.service = known[0];
    }
    if (p.qty) state.qty = p.qty;
    if (p.urgent) state.urgent = true;
    if (p.phone) { state.phone = p.phone; attachLead = true; }

    var ids = state.services || (state.service ? [state.service] : []);
    var services = ids.map(function (id) {
      return niche.services.filter(function (s) { return s.id === id; })[0];
    }).filter(Boolean);

    if (p.intent === "human") {
      return {
        reply: "Передам администратору. Напишите телефон и удобное время, он ответит в течение 15 минут в рабочее время. Если вопрос простой, я тоже могу ответить сразу.",
        quote: null, state: state, lead: attachLead
      };
    }
    if (p.intent === "greeting" && !services.length) {
      return { reply: niche.greeting, quote: null, state: state, lead: attachLead };
    }
    if (!services.length) {
      return {
        reply: "Понял вопрос, но пока не вижу, о какой услуге речь. Если нужен расчёт, назовите услугу и объём. " +
          hint(niche) + " Если услуги нет в списке, оставьте телефон: администратор посмотрит и ответит.",
        quote: null, state: state, lead: attachLead
      };
    }

    var primary = services[0];
    if (primary.per_unit && !state.qty) {
      return {
        reply: primary.name + ": " + rub(primary.price) + " " + primary.unit + ".\n" +
          "Скажите тираж, и я покажу цену с учётом скидки от объёма.\n" + niche.price_note,
        quote: null, state: state, lead: attachLead
      };
    }

    var blocks = [];
    services.slice(0, 2).forEach(function (svc) {
      var q = quote(niche, svc, svc.per_unit ? state.qty : null, !!state.urgent);
      if (!payload) {
        payload = {
          service: q.service.name, service_id: q.service.id, qty: q.qty,
          unit_price: q.unit_price, total_min: q.total_min, total_max: q.total_max,
          urgent: q.urgent_fee > 0
        };
      }
      blocks.push(quoteText(q, false));
    });
    state.stage = "quoted";

    var parts = [blocks.join("\n\n")];
    if (niche.price_note) parts.push(niche.price_note);

    var hasFree = services.slice(0, 2).some(function (s) { return s.price === 0; });
    if (hasFree || p.booking || p.intent === "booking") {
      parts.push("Свободное время: " + slots().join(", ") + ".");
      parts.push("Напишите время и телефон, запишу. Или назовите другое время, проверю.");
    } else {
      parts.push("Если подходит, оставьте телефон, передам администратору и зафиксирую цену.");
      if (niche.unknown) parts.push("Чего я не знаю: " + niche.unknown + ". Это уточнит администратор, врать не буду.");
    }
    if (p.phone) parts.push("Телефон записал: " + p.phone + ". Администратор свяжется в рабочее время.");

    return { reply: parts.join("\n"), quote: payload, state: state, lead: attachLead };
  }

  root.Bot = {
    parse: parse, quote: quote, quoteText: quoteText, answer: answer,
    hits: hits, tierFor: tierFor, pricePerLabel: pricePerLabel, slots: slots, rub: rub
  };
})(typeof window !== "undefined" ? window : globalThis);
