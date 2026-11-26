/* 100가지 질문 공통 차트. 각 페이지의 <script id="charts" type="application/json">에서 스펙을 읽는다. */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const SPECS = JSON.parse(document.getElementById("charts").textContent);
  const COL = { a: "var(--s-a)", b: "var(--s-b)", c: "var(--s-c)" };
  const col = c => COL[c] || c || COL.b;
  const fmtN = (n, d) => (n == null || isNaN(n)) ? "–" : Number(n).toLocaleString("ko-KR", { maximumFractionDigits: d == null ? 1 : d, minimumFractionDigits: 0 });
  function el(tag, attrs, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
  function txt(parent, x, y, s, attrs) { const t = el("text", Object.assign({ x, y }, attrs || {}), parent); t.textContent = s; return t; }
  function tipFor(box) {
    const t = document.createElement("div"); t.className = "tip"; t.hidden = true; box.appendChild(t);
    return { show(html, e) { t.innerHTML = html; t.hidden = false; const r = box.getBoundingClientRect(); let x = e.clientX - r.left; x = Math.max(70, Math.min(r.width - 70, x)); t.style.left = x + "px"; t.style.top = (e.clientY - r.top) + "px"; }, hide() { t.hidden = true; } };
  }
  function svgPt(svg, e) { const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; return p.matrixTransform(svg.getScreenCTM().inverse()); }
  function niceMax(v) { if (v <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))); const m = v / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p; }
  function ticks(max, n) { const out = []; for (let i = 0; i <= n; i++) out.push(max * i / n); return out; }
  const roundEnd = (x0, y, w, h, r) => { r = Math.min(r, w, h / 2); return `M${x0},${y} h${w - r} a${r},${r} 0 0 1 ${r},${r} v${h - 2 * r} a${r},${r} 0 0 1 ${-r},${r} h${-(w - r)} z`; };
  const roundTop = (x, y0, w, h, r) => { r = Math.min(r, w / 2, h); return `M${x},${y0} v${-(h - r)} a${r},${r} 0 0 1 ${r},${-r} h${w - 2 * r} a${r},${r} 0 0 1 ${r},${r} v${h - r} z`; };

  /* 가로 막대 */
  function hbar(svg, s, tip) {
    const rows = s.rows, W = s._W, L = Math.min(s.left || 150, Math.round(W * 0.4)), Rm = 80, top = 8, bh = s.bh || 24, gap = 12;
    const H = top + rows.length * (bh + gap) + 24; svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const max = s.max || niceMax(Math.max(...rows.map(r => r.v))), x = v => L + (W - L - Rm) * v / max;
    const g = el("g", { class: "tick" }, svg);
    ticks(max, 4).forEach(v => { el("line", { x1: x(v), x2: x(v), y1: top - 4, y2: H - 24, stroke: "var(--grid)" }, g); txt(g, x(v), H - 8, fmtN(v, 0), { "text-anchor": "middle" }); });
    rows.forEach((r, i) => {
      const y = top + i * (bh + gap);
      txt(svg, L - 10, y + bh / 2 + 4, r.l, { "text-anchor": "end" });
      const w = Math.max(3, x(r.v) - L);
      el("path", { d: roundEnd(L, y, w, bh, 4), fill: col(r.c || (r.hl ? "a" : "b")), opacity: r.hl || r.c ? 1 : 0.6 }, svg);
      txt(svg, L + w + 8, y + bh / 2 + 4, fmtN(r.v, s.d) + (s.unit || ""), { style: "font-family:var(--font-mono);fill:var(--ink)" });
      const hit = el("rect", { x: 0, y: y - gap / 2, width: W, height: bh + gap, fill: "transparent" }, svg);
      hit.addEventListener("mousemove", e => tip.show(r.tip || `${r.l}<br><b>${fmtN(r.v, s.d)}</b>${s.unit || ""}`, e)); hit.addEventListener("mouseleave", tip.hide);
    });
  }

  /* 세로 막대 */
  function col_(svg, s, tip) {
    const W = s._W, H = s.h || 260, L = 56, Rm = 14, T = 16, B = 34, n = s.labels.length;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const max = s.max || niceMax(Math.max(...s.values, s.ref || 0)), y = v => T + (H - T - B) * (1 - v / max);
    const bw = (W - L - Rm) / n, g = el("g", { class: "tick" }, svg);
    ticks(max, 4).forEach(v => { el("line", { x1: L, x2: W - Rm, y1: y(v), y2: y(v), stroke: v ? "var(--grid)" : "var(--axis)" }, g); txt(g, L - 8, y(v) + 4, fmtN(v, 0), { "text-anchor": "end" }); });
    const hl = new Set(s.hl || []), ev = Math.max(s.every || 1, Math.ceil(36 / bw));
    s.values.forEach((v, i) => {
      const x0 = L + i * bw + 1, w = Math.max(2, bw - 2), h = Math.max(0.5, y(0) - y(v));
      el("path", { d: roundTop(x0, y(0), w, h, Math.min(4, w / 2)), fill: hl.has(i) ? "var(--s-a)" : "var(--s-b)", opacity: hl.has(i) ? 1 : 0.6 }, svg);
      if (i % ev === 0) txt(g, x0 + w / 2, H - 12, s.labels[i], { "text-anchor": "middle" });
      const hit = el("rect", { x: L + i * bw, y: T, width: bw, height: H - T - B, fill: "transparent" }, svg);
      hit.addEventListener("mousemove", e => tip.show((s.tips && s.tips[i]) || `${s.labels[i]}<br><b>${fmtN(v, s.d)}</b>${s.unit || ""}`, e)); hit.addEventListener("mouseleave", tip.hide);
    });
    if (s.ref != null) {
      el("line", { x1: L, x2: W - Rm, y1: y(s.ref), y2: y(s.ref), stroke: "var(--ink)", "stroke-width": 1.5, "stroke-dasharray": "5 4" }, svg);
      txt(svg, W - Rm, y(s.ref) - 6, s.refLabel || "", { "text-anchor": "end", style: "fill:var(--ink)" });
    }
  }

  /* 선 (범주형 x) */
  function line(svg, s, tip) {
    const W = s._W, H = s.h || 260, L = 56, Rm = 20, T = 16, B = 34, n = s.x.length;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const all = s.series.flatMap(z => z.v.filter(v => v != null));
    const max = s.max || niceMax(Math.max(...all)), x = i => L + (W - L - Rm) * i / (n - 1), y = v => T + (H - T - B) * (1 - v / max);
    const g = el("g", { class: "tick" }, svg);
    ticks(max, 4).forEach(v => { el("line", { x1: L, x2: W - Rm, y1: y(v), y2: y(v), stroke: v ? "var(--grid)" : "var(--axis)" }, g); txt(g, L - 8, y(v) + 4, fmtN(v, 0) + (s.yunit || ""), { "text-anchor": "end" }); });
    const ev = Math.max(s.every || 1, Math.ceil(44 / ((W - L - Rm) / (n - 1)))); s.x.forEach((d, i) => { if (i % ev === 0) txt(g, x(i), H - 12, d, { "text-anchor": "middle" }); });
    (s.bands || []).forEach(b => { el("rect", { x: x(b[0]), y: T, width: x(b[1]) - x(b[0]), height: H - T - B, fill: "var(--accent-soft)" }, svg); if (b[2]) txt(svg, x(b[0]) + 4, T + 12, b[2], { style: "fill:var(--ink-2);font-size:11px" }); });
    s.series.forEach(z => {
      const d = z.v.map((v, i) => v == null ? "" : ((i && z.v[i - 1] != null) ? "L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1)).join("");
      el("path", { d, fill: "none", stroke: col(z.c), "stroke-width": 2, "stroke-linejoin": "round", "stroke-dasharray": z.dash || null }, svg);
    });
    (s.notes || []).forEach(a => { const v = s.series[a.s || 0].v[a.i]; txt(svg, x(a.i) + (a.dx || 8), y(v) + (a.dy || -8), a.t, { "text-anchor": a.anchor || "start", style: "fill:var(--ink)" }); });
    const cross = el("line", { y1: T, y2: H - B, stroke: "var(--axis)", visibility: "hidden" }, svg);
    const dots = s.series.map(z => el("circle", { r: 4, fill: col(z.c), stroke: "var(--surface)", "stroke-width": 2, visibility: "hidden" }, svg));
    const hit = el("rect", { x: L, y: T, width: W - L - Rm, height: H - T - B, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", e => {
      const q = svgPt(svg, e), i = Math.max(0, Math.min(n - 1, Math.round((q.x - L) / (W - L - Rm) * (n - 1))));
      cross.setAttribute("visibility", "visible"); cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i));
      s.series.forEach((z, k) => { const v = z.v[i]; dots[k].setAttribute("visibility", v == null ? "hidden" : "visible"); if (v != null) { dots[k].setAttribute("cx", x(i)); dots[k].setAttribute("cy", y(v)); } });
      tip.show(`${s.x[i]}<br>` + s.series.map(z => `${z.name || ""} <b>${fmtN(z.v[i], s.d)}</b>${s.yunit || ""}`).join("<br>"), e);
    });
    hit.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); dots.forEach(d => d.setAttribute("visibility", "hidden")); tip.hide(); });
  }

  /* 산점도·수치형 선 */
  function xy(svg, s, tip) {
    const W = s._W, H = s.h || 340, L = 60, Rm = 20, T = 18, B = 42;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const [x0, x1] = s.xd, [y0, y1] = s.yd;
    const lx = v => s.xlog ? Math.log10(Math.max(v, x0)) : v, ly = v => s.ylog ? Math.log10(Math.max(v, y0)) : v;
    const x = v => L + (W - L - Rm) * (lx(v) - lx(x0)) / (lx(x1) - lx(x0));
    const y = v => T + (H - T - B) * (1 - (ly(Math.min(Math.max(v, y0), y1)) - ly(y0)) / (ly(y1) - ly(y0)));
    const g = el("g", { class: "tick" }, svg);
    (s.yt || ticks(y1, 4)).forEach(v => { el("line", { x1: L, x2: W - Rm, y1: y(v), y2: y(v), stroke: v === y0 ? "var(--axis)" : "var(--grid)" }, g); txt(g, L - 8, y(v) + 4, fmtN(v, 1), { "text-anchor": "end" }); });
    (s.xt || ticks(x1, 4)).forEach(v => txt(g, x(v), H - B + 18, fmtN(v, 1) + (s.xunit || ""), { "text-anchor": "middle" }));
    if (s.xlab) txt(svg, W - Rm, H - 4, s.xlab, { "text-anchor": "end" });
    if (s.ylab) txt(svg, L, T - 6, s.ylab);
    const all = [];
    s.series.forEach(z => {
      if (z.kind === "line") {
        const d = z.pts.map((p, i) => (i ? "L" : "M") + x(p[0]).toFixed(1) + "," + y(p[1]).toFixed(1)).join("");
        el("path", { d, fill: "none", stroke: col(z.c), "stroke-width": 2.5, "stroke-dasharray": z.dash || null, "stroke-linejoin": "round" }, svg);
        if (z.marks) z.pts.forEach(p => el("circle", { cx: x(p[0]), cy: y(p[1]), r: 4, fill: col(z.c), stroke: "var(--surface)", "stroke-width": 2 }, svg));
      } else {
        const gp = el("g", {}, svg);
        z.pts.forEach(p => el("circle", { cx: x(p[0]).toFixed(1), cy: y(p[1]).toFixed(1), r: z.r || 2.6, fill: col(z.c), "fill-opacity": z.op || 0.5, stroke: "var(--surface)", "stroke-width": 0.5 }, gp));
      }
      if (z.tip !== false) z.pts.forEach(p => all.push([p, z]));
    });
    (s.labels || []).forEach(a => txt(svg, x(a[0]), y(a[1]), a[2], { "text-anchor": a[3] || "start", style: "fill:var(--ink)" }));
    const hit = el("rect", { x: L, y: T, width: W - L - Rm, height: H - T - B, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", e => {
      const q = svgPt(svg, e); let best = null, bd = 196;
      for (const [p, z] of all) { const dx = x(p[0]) - q.x, dy = y(p[1]) - q.y, dd = dx * dx + dy * dy; if (dd < bd) { bd = dd; best = [p, z]; } }
      if (!best) return tip.hide();
      const [p, z] = best; const f = s.tipf || ["x", "y"];
      tip.show((z.name ? z.name + "<br>" : "") + (p[2] != null && s.tip3 ? s.tip3 + " <b>" + fmtN(p[2], 0) + "</b><br>" : "") + `${f[0]} <b>${fmtN(p[0], 1)}</b> · ${f[1]} <b>${fmtN(p[1], 1)}</b>`, e);
    });
    hit.addEventListener("mouseleave", tip.hide);
  }

  /* 점과 오차막대 */
  function ci(svg, s, tip) {
    const rows = s.rows, W = s._W, L = Math.min(s.left || 130, Math.round(W * 0.36)), Rm = 60, top = 10, rh = 34;
    const H = top + rows.length * rh + 26; svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const [a, b] = s.xd, x = v => L + (W - L - Rm) * (v - a) / (b - a);
    const g = el("g", { class: "tick" }, svg);
    ticks(b - a, 4).map(v => v + a).forEach(v => { el("line", { x1: x(v), x2: x(v), y1: top - 4, y2: H - 26, stroke: "var(--grid)" }, g); txt(g, x(v), H - 8, fmtN(v, 0) + (s.unit || ""), { "text-anchor": "middle" }); });
    rows.forEach((r, i) => {
      const y = top + i * rh + rh / 2;
      txt(svg, L - 10, y + 4, r.l, { "text-anchor": "end" });
      el("line", { x1: x(r.lo), x2: x(r.hi), y1: y, y2: y, stroke: "var(--s-b)", "stroke-width": 2 }, svg);
      [r.lo, r.hi].forEach(v => el("line", { x1: x(v), x2: x(v), y1: y - 6, y2: y + 6, stroke: "var(--s-b)", "stroke-width": 2 }, svg));
      el("circle", { cx: x(r.v), cy: y, r: 5, fill: "var(--s-a)", stroke: "var(--surface)", "stroke-width": 2 }, svg);
      const hit = el("rect", { x: 0, y: y - rh / 2, width: W, height: rh, fill: "transparent" }, svg);
      hit.addEventListener("mousemove", e => tip.show(`${r.l}<br><b>${fmtN(r.v, 1)}</b>${s.unit || ""} (95% 구간 ${fmtN(r.lo, 2)}–${fmtN(r.hi, 2)})`, e)); hit.addEventListener("mouseleave", tip.hide);
    });
  }

  /* 격자(표 색칠) */
  function grid(box, s) {
    const max = Math.max(...s.values.flat().filter(v => v != null));
    let h = `<div class="tscroll"><table class="grid"><tr><th>${s.corner || ""}</th>${s.cols.map(c => `<th>${c}</th>`).join("")}</tr>`;
    s.values.forEach((row, i) => {
      h += `<tr><th>${s.rows[i]}</th>` + row.map((v, j) => {
        const pct = v == null ? 0 : Math.round(v / max * 70) + 6, n = s.ns ? s.ns[i][j] : null, thin = n != null && n < 30;
        return `<td style="background:color-mix(in srgb, var(--s-b) ${pct}%, var(--surface))" title="${n != null ? "Tract " + n + "곳" : ""}"><span class="${pct > 50 ? "inv" : ""}">${fmtN(v, 0)}</span>${thin ? '<sup>*</sup>' : ""}</td>`;
      }).join("") + "</tr>";
    });
    box.querySelector(".gridwrap").innerHTML = h + "</table></div>";
  }

  function table(s) {
    if (s.type === "hbar") return [["항목", s.unit ? "값(" + s.unit.trim() + ")" : "값"], ...s.rows.map(r => [r.l, fmtN(r.v, s.d)])];
    if (s.type === "col") return [["구간", "값"], ...s.labels.map((l, i) => [l, fmtN(s.values[i], s.d)])];
    if (s.type === "line") return [["", ...s.series.map(z => z.name || "값")], ...s.x.map((l, i) => [l, ...s.series.map(z => fmtN(z.v[i], s.d))])];
    if (s.type === "ci") return [["집단", "값", "95% 하한", "95% 상한"], ...s.rows.map(r => [r.l, fmtN(r.v, 1), fmtN(r.lo, 2), fmtN(r.hi, 2)])];
    if (s.type === "xy" && s.table) return s.table;
    return null;
  }

  function render(box, s) {
    box._spec = s;
    s = Object.assign({}, s, { _W: Math.max(320, Math.min(700, Math.round(box.clientWidth - 32))) });
    const tip = box._tip || (box._tip = tipFor(box));
    const svg = box.querySelector("svg"); if (svg) svg.innerHTML = "";
    if (s.type === "grid") grid(box, s); else ({ hbar, col: col_, line, xy, ci })[s.type](svg, s, tip);
    const note = box.querySelector(".vnote"); if (note) note.textContent = s.note || "";
    const tb = box.querySelector("table.tv"), t = table(s);
    if (tb) { if (t) { tb.innerHTML = `<tr>${t[0].map(c => `<th>${c}</th>`).join("")}</tr>` + t.slice(1).map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join(""); tb.closest("details").hidden = false; } else tb.closest("details").hidden = true; }
  }

  let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => document.querySelectorAll(".chart[data-c]").forEach(b => { if (b._spec && b._spec.type !== "grid") render(b, b._spec); }), 150); });
  document.querySelectorAll(".chart[data-c]").forEach(box => {
    const base = SPECS[box.dataset.c];
    if (!base.views) return render(box, base);
    const seg = box.querySelector(".seg");
    base.views.forEach((v, i) => {
      const b = document.createElement("button"); b.type = "button"; b.textContent = v.label; seg.appendChild(b);
      b.addEventListener("click", () => { seg.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b)); render(box, Object.assign({}, base, v)); });
      if (i === 0) b.click();
    });
  });
})();
