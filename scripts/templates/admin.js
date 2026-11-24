/* Админка статической версии: читает заявки из localStorage и отдаёт CSV. */
(function () {
  "use strict";
  var rows = document.getElementById("rows");
  var empty = document.getElementById("empty");
  var csvLink = document.getElementById("csv");

  function rub(v) {
    if (v === null || v === undefined) return "";
    return Number(v).toLocaleString("ru-RU") + " ₽";
  }

  function quoteText(q) {
    if (!q) return "";
    var total = q.total_max > q.total_min ? rub(q.total_min) + " до " + rub(q.total_max) : rub(q.total_min);
    return q.service + (q.qty ? ", " + q.qty + " шт" : "") + ": " + total;
  }

  function load() {
    var all = JSON.parse(localStorage.getItem("leads") || "[]").reverse();
    rows.innerHTML = "";
    document.getElementById("n-leads").textContent = all.length;
    document.getElementById("n-phones").textContent = all.filter(function (r) { return r.phone; }).length;
    document.getElementById("n-sessions").textContent = all.length;
    empty.style.display = all.length ? "none" : "block";

    all.forEach(function (r, i) {
      var tr = document.createElement("tr");
      [String(all.length - i), r.niche, r.phone || "нет", (r.question || "").slice(0, 90),
       quoteText(r.quote), (r.at || "").slice(0, 16).replace("T", " ")].forEach(function (cell, idx) {
        var td = document.createElement("td");
        td.textContent = cell;
        if (idx === 4 || idx === 5) td.className = "muted";
        tr.appendChild(td);
      });
      rows.appendChild(tr);
    });

    var csv = "\uFEFFid;ниша;телефон;вопрос;смета;когда\n" + all.map(function (r) {
      return [r.id, r.niche, r.phone, (r.question || "").replace(/;/g, ","),
              quoteText(r.quote).replace(/;/g, ","), r.at].join(";");
    }).join("\n");
    csvLink.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    csvLink.setAttribute("download", "leads.csv");
  }

  document.getElementById("clear").addEventListener("click", function () {
    if (confirm("Очистить заявки в этом браузере?")) {
      localStorage.removeItem("leads");
      load();
    }
  });

  load();
})();
