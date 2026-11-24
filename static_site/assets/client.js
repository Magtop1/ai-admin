/* Клиент демо для статической версии: каталог грузим из catalog.json,
 * заявки складываем в localStorage. Сервер не нужен. */
(function () {
  "use strict";
  var nicheSlug = document.body.getAttribute("data-niche");
  var log = document.getElementById("log");
  var form = document.getElementById("form");
  var inp = document.getElementById("inp");
  var state = {};
  var sid = "s" + Math.random().toString(36).slice(2, 10);

  function el(tag, cls) { var e = document.createElement(tag); if (cls) e.className = cls; return e; }

  function bubble(text, who) {
    var row = el("div", "msg " + who);
    var b = el("div", "bubble");
    b.textContent = text;
    row.appendChild(b);
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  function quoteCard(q) {
    if (!q) return;
    var row = el("div", "msg bot");
    var card = el("div", "quote-card");
    var total = q.total_max > q.total_min
      ? Bot.rub(q.total_min) + " до " + Bot.rub(q.total_max)
      : Bot.rub(q.total_min);
    card.innerHTML =
      '<div class="t">смета из прайса</div>' +
      '<div class="n">' + q.service + (q.qty ? ", " + q.qty + " шт" : "") + "</div>" +
      "<div>Итого: " + total + (q.urgent ? " · срочно" : "") + "</div>";
    row.appendChild(card);
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  function saveLead(niche, q, question) {
    var all = JSON.parse(localStorage.getItem("leads") || "[]");
    all.push({ id: all.length + 1, niche: niche, phone: state.phone || "", question: question,
               quote: q, at: new Date().toISOString() });
    localStorage.setItem("leads", JSON.stringify(all));
    var note = el("div", "lead-ok");
    note.textContent = "Заявка №" + all.length + " записана. Посмотреть: раздел Заявки.";
    log.appendChild(note);
    log.scrollTop = log.scrollHeight;
  }

  function send(text) {
    if (!text) return;
    bubble(text, "user");
    inp.value = "";
    var res = Bot.answer(catalog[nicheSlug], state, text);
    state = res.state;
    bubble(res.reply, "bot");
    quoteCard(res.quote);
    if (res.lead && state.phone) saveLead(nicheSlug, res.quote, text);
    inp.focus();
  }

  var catalog = {};
  fetch("../assets/catalog.json")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      catalog = data;
      bubble(data[nicheSlug].greeting, "bot");
      inp.focus();
    })
    .catch(function () {
      bubble("Не удалось загрузить прайс. Откройте страницу через локальный сервер или с сайта.", "bot");
    });

  form.addEventListener("submit", function (e) { e.preventDefault(); send(inp.value.trim()); });
  Array.prototype.forEach.call(document.querySelectorAll(".quick button"), function (b) {
    b.addEventListener("click", function () { send(b.getAttribute("data-q")); });
  });
})();
