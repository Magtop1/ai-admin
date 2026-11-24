/* Клиент бота: без фреймворков и без CDN. Только fetch и DOM. */
(function () {
  const log = document.getElementById("log");
  const form = document.getElementById("form");
  const inp = document.getElementById("inp");
  const slug = window.DEMO.slug;
  const sid = (() => {
    const k = "sid:" + slug;
    let v = sessionStorage.getItem(k);
    if (!v) {
      v = "s" + Math.random().toString(36).slice(2, 10);
      sessionStorage.setItem(k, v);
    }
    return v;
  })();

  function bubble(text, who) {
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.justifyContent = who === "user" ? "flex-end" : "flex-start";
    const box = document.createElement("div");
    box.textContent = text;
    box.style.whiteSpace = "pre-wrap";
    box.style.maxWidth = "86%";
    box.style.padding = "10px 12px";
    box.style.borderRadius = "12px";
    box.style.fontSize = "14.5px";
    box.style.lineHeight = "1.5";
    if (who === "user") {
      box.style.background = "#101318";
      box.style.color = "#fff";
      box.style.borderBottomRightRadius = "4px";
    } else {
      box.style.background = "#f6f7f9";
      box.style.border = "1px solid #e4e8ee";
      box.style.borderBottomLeftRadius = "4px";
    }
    row.appendChild(box);
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  function quoteCard(q) {
    if (!q) return;
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.justifyContent = "flex-start";
    const card = document.createElement("div");
    card.style.border = "1px solid #cfe0ff";
    card.style.background = "#f5f9ff";
    card.style.borderRadius = "12px";
    card.style.padding = "10px 12px";
    card.style.fontSize = "13.5px";
    card.style.maxWidth = "86%";
    const rub = (v) => v.toLocaleString("ru-RU") + " ₽";
    const total = q.total_max > q.total_min ? rub(q.total_min) + " до " + rub(q.total_max) : rub(q.total_min);
    card.innerHTML =
      '<div style="font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:#5b6b84">смета из базы</div>' +
      '<div style="font-weight:700;margin:4px 0">' + q.service + (q.qty ? ", " + q.qty + " шт" : "") + "</div>" +
      '<div style="color:#2a3038">Итого: ' + total + (q.urgent ? " · срочно" : "") + "</div>";
    row.appendChild(card);
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  let busy = false;
  async function send(text) {
    if (!text || busy) return;
    busy = true;
    bubble(text, "user");
    inp.value = "";
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug: slug, session_id: sid, text: text }),
      });
      const data = await r.json();
      if (r.ok) {
        bubble(data.reply, "bot");
        quoteCard(data.quote);
        if (data.lead_id) {
          const note = document.createElement("div");
          note.className = "muted";
          note.style.fontSize = "12px";
          note.style.color = "#137a4b";
          note.textContent = "Заявка №" + data.lead_id + " записана в базу";
          log.appendChild(note);
          log.scrollTop = log.scrollHeight;
        }
      } else {
        bubble("Не получилось отправить: " + (data.error || r.status), "bot");
      }
    } catch (e) {
      bubble("Сеть недоступна, попробуйте ещё раз.", "bot");
    } finally {
      busy = false;
      inp.focus();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    send(inp.value.trim());
  });
  document.querySelectorAll("button.quick").forEach((b) => {
    b.addEventListener("click", () => send(b.dataset.q));
  });

  bubble(window.DEMO.greeting, "bot");
  inp.focus();
})();
