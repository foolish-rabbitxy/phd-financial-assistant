"use strict";

const $ = (id) => document.getElementById(id);
const SVG = "http://www.w3.org/2000/svg";
let csrf = "";
let range = ["3m", "1y", "all"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "all";

const fmt = {
  num: (v, d = 0) => (v == null ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d })),
  usd: (v, d = 2) => (v == null ? "–" : `${v < 0 ? "−" : ""}$${fmt.num(Math.abs(v), d)}`),
  pct: (v) => (v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${fmt.num(Math.abs(v), 2)}%`),
  date: (s) => (s ? new Date(`${s}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }) : "–"),
};

function el(tag, attrs = {}, text) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, ...(opts.headers || {}) } });
  if (res.status === 401) { location.href = "/login"; throw new Error("login required"); }
  const body = await res.json().catch(() => ({}));
  return { ok: res.ok, ...body };
}

const signClass = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
function table(id, headers, rows) {
  const head = el("tr");
  headers.forEach((h) => head.append(el("th", {}, h)));
  $(id).replaceChildren(head, ...(rows.length ? rows : [(() => { const tr = el("tr"); const td = el("td", { colspan: headers.length, class: "muted" }, "Nothing yet"); tr.append(td); return tr; })()]));
}
function row(cells) {
  const tr = el("tr");
  cells.forEach((c) => {
    if (c instanceof Node) { const td = el("td"); td.append(c); tr.append(td); }
    else if (Array.isArray(c)) tr.append(el("td", { class: c[1] }, c[0]));
    else tr.append(el("td", {}, c));
  });
  return tr;
}

// ---------------------------------------------------------------- scorecard
const VERDICT = { behind: ["critical", "Behind"], ahead: ["good", "Ahead"], even: ["neutral", "Even"] };

function renderWindow(box, title, w) {
  if (!w) { box.replaceChildren(el("div", { class: "label" }, title), el("p", { class: "muted" }, "Not enough history yet")); return; }
  const [level, word] = VERDICT[w.verdict];
  const head = el("div", { class: "tile-head" });
  const badgeText = w.verdict === "even" ? word : `${word} ${fmt.num(Math.abs(w.diff_pts), 1)} pts`;
  head.append(el("span", { class: "label" }, `${title} · ${fmt.date(w.start)}`), el("span", { class: `badge ${level}` }, badgeText));
  const grid = el("div", { class: "vs" });
  const side = (name, pct, val, cls) => {
    const d = el("div", { class: "vs-side" });
    d.append(el("div", { class: "vs-name" }, name), el("div", { class: `vs-pct ${signClass(pct)}` }, fmt.pct(pct)), el("div", { class: "sub" }, `${fmt.usd(val, 0)} now`));
    d.classList.add(cls);
    return d;
  };
  grid.append(side("Bot", w.bot_pct, w.bot_value, "bot"), el("div", { class: "vs-mid" }, "vs"), side("S&P 500", w.spy_pct, w.spy_value, "spy"));
  box.replaceChildren(head, grid);
}

function renderScorecard(d) {
  const w = d.windows.since_open;
  const badge = $("verdict-badge"), pill = $("verdict-pill"), card = $("verdict-card");
  if (w) {
    const [level, word] = VERDICT[w.verdict];
    badge.className = `badge ${level}`;
    badge.textContent = word;
    card.dataset.level = level;
    $("verdict-text").textContent = w.verdict === "even"
      ? "The bot is keeping pace with the S&P 500"
      : `The bot is ${w.verdict} the S&P 500 by ${fmt.num(Math.abs(w.diff_pts), 1)} percentage points`;
    pill.className = `pill ${level === "neutral" ? "" : level}`;
    pill.textContent = `${word} ${fmt.num(Math.abs(w.diff_pts), 1)} pts`;
  }
  renderWindow($("w-open"), "Since the account opened", w);
  renderWindow($("w-auto"), "Since the autopilot started", d.windows.since_autopilot);
}

// ---------------------------------------------------------------- tiles & tables
function renderTiles(d) {
  const a = d.account, eq = Number(a.equity), last = Number(a.last_equity), cash = Number(a.cash);
  $("t-equity").textContent = fmt.usd(eq);
  $("t-equity-sub").textContent = "started at $100,000.00";
  const chg = eq - last, chgPct = last ? (chg / last) * 100 : 0;
  $("t-today").textContent = `${chg >= 0 ? "+" : "−"}${fmt.usd(Math.abs(chg))}`;
  $("t-today").className = `value ${signClass(chg)}`;
  const tb = $("t-today-badge");
  tb.className = `badge ${chg > 0 ? "good" : chg < 0 ? "critical" : "neutral"}`;
  tb.textContent = fmt.pct(chgPct);
  $("t-cash").textContent = fmt.usd(cash);
  $("t-cash-sub").textContent = eq ? `${fmt.num((cash / eq) * 100, 1)}% of the account` : "";
  $("t-pos").textContent = d.positions.length;
  $("t-pos-sub").textContent = d.positions.map((p) => p.symbol).join(" · ");
  const t = d.timer || {};
  $("t-next").textContent = t.next ? t.next.replace(/:00 [A-Z]{3}$/, "").replace(/^(\w{3}) (\d{4})-(\d{2})-(\d{2})/, (_, w, y, m, dd) => `${w} ${fmt.date(`${y}-${m}-${dd}`).replace(`, ${y}`, "")},`) : "Not scheduled";
  const nb = $("t-next-badge");
  nb.className = `badge ${t.active ? "good" : "critical"}`;
  nb.textContent = t.active ? "On" : "Off";
  const lastRow = d.weekly[0];
  $("t-last").textContent = lastRow ? fmt.date(lastRow.date) : "None yet";
  $("t-last-sub").textContent = lastRow ? `bot ${fmt.pct(lastRow.bot_pct)} vs S&P ${fmt.pct(lastRow.spy_pct)} since first run` : "";
}

function renderHoldings(d) {
  const total = d.positions.reduce((s, p) => s + p.value, 0) || 1;
  table("holdings", ["Stock", "Shares", "Value", "Gain / loss", "Share of portfolio"],
    [...d.positions].sort((a, b) => b.value - a.value).map((p) => {
      const bar = el("span", { class: "weight" });
      const fill = el("span");
      fill.style.width = `${(p.value / total) * 100}%`;
      bar.append(fill);
      const w = el("span", { class: "weight-row" });
      w.append(bar, el("span", {}, `${fmt.num((p.value / total) * 100, 1)}%`));
      return row([p.symbol, fmt.num(p.qty), fmt.usd(p.value), [`${p.pl >= 0 ? "+" : "−"}${fmt.usd(Math.abs(p.pl))} (${fmt.pct(p.pl_pct)})`, signClass(p.pl)], w]);
    }));
}

function renderWeekly(d) {
  table("weekly", ["Monday", "Bot value", "Bot", "S&P 500", "Bot vs S&P"],
    d.weekly.map((r) => {
      const diff = r.bot_pct - r.spy_pct;
      return row([fmt.date(r.date), fmt.usd(r.equity, 0), [fmt.pct(r.bot_pct), signClass(r.bot_pct)], [fmt.pct(r.spy_pct), signClass(r.spy_pct)], [`${diff >= 0 ? "+" : "−"}${fmt.num(Math.abs(diff), 2)} pts`, signClass(diff)]]);
    }));
}

function renderTrades(d) {
  table("trades", ["Date", "Trade", "Shares", "Avg price", "Total"],
    d.trades.map((t) => row([fmt.date(t.date), [`${t.side === "buy" ? "Buy" : "Sell"} ${t.symbol}`, t.side === "buy" ? "buy" : "sell"], fmt.num(t.qty), fmt.usd(t.price), fmt.usd(t.value, 0)])));
}

async function refresh() {
  let d;
  try { d = await api("/api/summary"); } catch { return; }
  csrf = d.csrf;
  $("updated").textContent = d.as_of ? `Data through ${fmt.date(d.as_of)}` : "";
  const errs = $("errors");
  errs.textContent = d.errors.length ? `Some data couldn't be refreshed: ${d.errors.join(" · ")}` : "";
  errs.classList.toggle("hidden", !d.errors.length);
  renderScorecard(d);
  renderTiles(d);
  renderHoldings(d);
  renderWeekly(d);
  renderTrades(d);
}

// ---------------------------------------------------------------- chart
function niceScale(lo, hi) {
  const span = hi - lo || 1, raw = span / 4, p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => s >= raw);
  return { lo: Math.floor(lo / step) * step, hi: Math.ceil(hi / step) * step, step };
}

function drawCompare(series) {
  const fig = $("c-compare");
  const W = Math.max(fig.clientWidth || 700, 300), H = 260, L = 70, R = 110, T = 10, B = 24;
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Bot account value compared with the same money in the S&P 500");
  const add = (tag, attrs, text) => {
    const e = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (text != null) e.textContent = text;
    svg.append(e);
    return e;
  };
  fig.replaceChildren(svg);
  if (series.length < 2) { add("text", { x: W / 2, y: H / 2, "text-anchor": "middle", class: "empty" }, "Not enough history yet"); return; }
  const vals = series.flatMap((p) => [p.bot, p.spy]).filter((v) => v != null);
  const { lo, hi, step } = niceScale(Math.min(...vals), Math.max(...vals));
  const t = series.map((p) => new Date(`${p.date}T12:00:00`).getTime());
  const x = (i) => L + ((t[i] - t[0]) / (t[t.length - 1] - t[0] || 1)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  for (let v = lo; v <= hi + 1e-9; v += step) {
    add("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: v === lo ? "axis" : "grid" });
    add("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" }, `$${fmt.num(v)}`);
  }
  for (let k = 0; k <= 3; k++) {
    const i = Math.round((k / 3) * (series.length - 1));
    add("text", { x: x(i), y: H - 6, "text-anchor": k === 0 ? "start" : k === 3 ? "end" : "middle" },
      new Date(t[i]).toLocaleDateString([], { month: "short", year: "2-digit" }));
  }
  const path = (key) => series.map((p, i) => (p[key] == null ? "" : `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`)).join("");
  add("path", { d: path("spy"), class: "line l-spy" });
  add("path", { d: path("bot"), class: "line l-bot" });
  const last = series[series.length - 1];
  const labels = [{ y: y(last.bot) + 4, t: "Bot", c: "lab-bot" }, { y: y(last.spy) + 4, t: "S&P 500 ≈ FXAIX", c: "lab-spy" }].sort((a, b) => a.y - b.y);
  if (labels[1].y - labels[0].y < 13) labels[1].y = labels[0].y + 13;
  labels.forEach((l) => add("text", { x: W - R + 6, y: l.y, class: `endlabel ${l.c}` }, l.t));

  const cross = add("line", { y1: T, y2: H - B, class: "cross", visibility: "hidden" });
  const dots = ["l-bot", "l-spy"].map((c) => add("circle", { r: 4, class: `dot ${c}`, visibility: "hidden" }));
  const hit = add("rect", { x: L, y: 0, width: W - L - R, height: H, fill: "transparent" });
  const tip = $("tooltip");
  hit.addEventListener("pointermove", (ev) => {
    const r = svg.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    let i = 0;
    for (let j = 1; j < series.length; j++) if (Math.abs(x(j) - px) < Math.abs(x(i) - px)) i = j;
    const p = series[i];
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    [p.bot, p.spy].forEach((v, k) => { dots[k].setAttribute("cx", x(i)); dots[k].setAttribute("cy", y(v)); dots[k].setAttribute("visibility", "visible"); });
    const gap = p.bot - p.spy;
    const line = (cls, name, v) => { const d = el("div"); d.append(el("i", { class: cls }), `${name}: ${fmt.usd(v)}`); return d; };
    tip.replaceChildren(el("div", { class: "t" }, fmt.date(p.date)), line("bg-bot", "Bot", p.bot), line("bg-spy", "S&P 500", p.spy),
      el("div", { class: signClass(gap) }, `${gap >= 0 ? "Ahead" : "Behind"} by ${fmt.usd(Math.abs(gap), 0)}`));
    tip.classList.remove("hidden");
    tip.style.left = `${Math.min(ev.clientX + 14, innerWidth - tip.offsetWidth - 8)}px`;
    tip.style.top = `${ev.clientY + 14}px`;
  });
  hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); dots.forEach((d) => d.setAttribute("visibility", "hidden")); tip.classList.add("hidden"); });
}

let lastSeries = [];
async function loadChart() {
  try {
    const r = await api(`/api/chart?range=${range}`);
    if (r.ok) { lastSeries = r.series; drawCompare(lastSeries); }
  } catch { /* retried on next tick */ }
}
function markRange() { for (const b of $("range-seg").children) b.classList.toggle("on", b.dataset.range === range); }
$("range-seg").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  range = b.dataset.range;
  history.replaceState(null, "", `#${range}`);
  markRange();
  loadChart();
});
let rt;
addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => drawCompare(lastSeries), 150); });

// ---------------------------------------------------------------- picks
async function loadPicks() {
  let r;
  try { r = await api("/api/picks"); } catch { return; }
  const p = r.picks;
  if (!p) { $("picks-meta").textContent = r.error || "Scoring today's stocks… (about 10 seconds)"; setTimeout(loadPicks, 5000); return; }
  $("picks-meta").textContent = `${p.count} stocks qualify today · scored ${new Date(r.computed_at * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  $("alloc").replaceChildren(...p.allocation.map((a) => {
    const d = el("div", { class: "alloc-row" });
    const head = el("div", { class: "alloc-head" });
    head.append(el("strong", {}, a.symbol), el("span", { class: "muted small" }, a.sector || ""),
      el("span", { class: `small ${a.held ? "" : "up"}` }, a.held ? "● held" : "new"));
    d.append(head, el("p", { class: "muted small" }, a.why));
    return d;
  }));
  const pct = (v, d = 0) => (v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${fmt.num(Math.abs(v * 100), d)}%`);
  table("picks", ["#", "Stock", "", "Sector", "Score", "12-mo mom.", "6-mo mom.", "Volatility", "P/E", "Dividend", "ROE"],
    p.top.map((s) => row([String(s.rank), s.symbol, `${s.picked ? "✓" : ""}${s.held ? " ●" : ""}`, s.sector || "–",
      fmt.num(s.score, 3), [pct(s.mom_12_1), signClass(s.mom_12_1)], [pct(s.mom_6_1), signClass(s.mom_6_1)],
      s.vol_1y != null ? `${fmt.num(s.vol_1y * 100, 2)}%/day` : "–", fmt.num(s.pe_ratio, 1),
      s.dividend_yield != null ? `${fmt.num(s.dividend_yield, 2)}%` : "–", pct(s.roe)])));
}

// ---------------------------------------------------------------- settings
$("pw-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, msg = $("pw-msg");
  msg.className = "msg"; msg.textContent = "Saving…";
  const r = await api("/api/password", { method: "POST", body: JSON.stringify({ current: f.current.value, new: f.new.value, repeat: f.repeat.value }) });
  msg.className = `msg ${r.ok ? "ok" : "err"}`;
  msg.textContent = r.message || r.error;
  if (r.ok) f.reset();
});

markRange();
refresh();
loadChart();
loadPicks();
setInterval(() => { if (!document.hidden) refresh(); }, 60000);
setInterval(loadPicks, 600000);
