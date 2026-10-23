const PALETTE = ["#0f766e", "#f59e0b", "#6366f1", "#ec4899", "#ef4444", "#0ea5e9", "#84cc16", "#a855f7", "#14b8a6", "#f97316"];
const OTHER_COLOR = "#94a3b8";

function localDate(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const state = {
  month: localDate().slice(0, 7),
  view: "home",
  categories: [],
  filter: null,
  query: "",
  editing: null,
  pollTimer: null,
};

const $ = (sel) => document.querySelector(sel);
const money = (n) => "$" + Math.round(n || 0).toLocaleString("zh-TW");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function colorOf(cat) {
  if (cat === "其他") return OTHER_COLOR;
  const i = state.categories.indexOf(cat);
  return PALETTE[(i < 0 ? 0 : i) % PALETTE.length];
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

function toast(text, ms = 2600) {
  const el = $("#toast");
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (el.hidden = true), ms);
}

function shiftMonth(delta) {
  const [y, m] = state.month.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  state.month = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  refresh();
}

function monthLabel() {
  const [y, m] = state.month.split("-").map(Number);
  return `${y} 年 ${m} 月`;
}

function go(view) {
  state.view = view;
  for (const v of ["home", "list", "settings"]) $(`#view-${v}`).hidden = v !== view;
  document.querySelectorAll(".tabbar [data-goto]").forEach((b) => b.classList.toggle("active", b.dataset.goto === view));
  window.scrollTo({ top: 0 });
  refresh();
}

function statusTag(e) {
  if (e.status === "processing") return `<span class="tag proc">辨識中</span>`;
  if (e.status === "review") return `<span class="tag review">待確認</span>`;
  if (e.status === "error") return `<span class="tag error">${e.message?.includes("記過") ? "重複" : "失敗"}</span>`;
  return "";
}

function entryHTML(e) {
  const thumb = e.thumb
    ? `<img class="thumb" src="/receipts/${esc(e.thumb)}" loading="lazy" alt="">`
    : `<div class="thumb" style="background:${colorOf(e.category)}">${esc((e.category || "其")[0])}</div>`;
  const right = e.status === "processing" ? `<div class="spinner"></div>` : `<div class="amt">${e.amount != null ? money(e.amount) : "—"}</div>`;
  const title = e.status === "processing" ? "正在讀取發票…" : e.merchant || "未填商家";
  const d = e.date ? e.date.slice(5).replace("-", "/") : "";
  return `<li class="entry" data-id="${e.id}">
    ${thumb}
    <div class="main">
      <div class="title">${esc(title)}</div>
      <div class="sub">${d ? `<span>${d}</span>` : ""}${e.category && e.status !== "processing" ? `<span class="tag cat">${esc(e.category)}</span>` : ""}${statusTag(e)}</div>
    </div>
    ${right}
  </li>`;
}

function renderEntries(el, list, emptyText) {
  el.innerHTML = list.length ? list.map(entryHTML).join("") : `<li class="empty-state">${emptyText}</li>`;
}

function renderDonut(byCat, total) {
  byCat = byCat.filter((r) => r.total > 0);
  const svg = $("#donut");
  const r = 46, c = 2 * Math.PI * r;
  let offset = 0;
  let html = `<circle cx="60" cy="60" r="${r}" stroke="var(--line)"></circle>`;
  for (const row of byCat) {
    const len = total ? (row.total / total) * c : 0;
    html += `<circle cx="60" cy="60" r="${r}" stroke="${colorOf(row.category)}" stroke-dasharray="${Math.max(len - 1.5, 0)} ${c}" stroke-dashoffset="${-offset}"></circle>`;
    offset += len;
  }
  svg.innerHTML = html;
  $("#legend").innerHTML = byCat.length
    ? byCat.slice(0, 6).map((r) => `<li><i style="background:${colorOf(r.category)}"></i><span>${esc(r.category)}</span><b>${money(r.total)}</b></li>`).join("")
    : `<li class="empty">這個月還沒有記錄，按下面的「拍發票」開始。</li>`;
}

function renderBars(daily) {
  const [y, m] = state.month.split("-").map(Number);
  const days = new Date(y, m, 0).getDate();
  const map = Object.fromEntries(daily.map((d) => [Number(d.date.slice(8, 10)), d.total]));
  const max = Math.max(1, ...Object.values(map));
  const today = new Date();
  const isThisMonth = today.getFullYear() === y && today.getMonth() + 1 === m;
  let html = "";
  for (let d = 1; d <= days; d++) {
    const v = map[d] || 0;
    const cls = ["bar", v ? "" : "zero", isThisMonth && d === today.getDate() ? "today" : ""].join(" ");
    const label = d === 1 || d % 5 === 0 ? `<span>${d}</span>` : "";
    html += `<div class="${cls}" title="${m}/${d} ${money(v)}"><div style="height:${(v / max) * 100}%"></div>${label}</div>`;
  }
  $("#dailyBars").innerHTML = html;
}

async function renderHome() {
  const [sum, list] = await Promise.all([
    api(`/api/summary?month=${state.month}`),
    api(`/api/expenses?month=${state.month}`),
  ]);
  $("#monthTotal").textContent = money(sum.total);
  let cmp = `${sum.count} 筆`;
  if (sum.previous_total > 0) {
    const diff = sum.total - sum.previous_total;
    const pct = Math.round((Math.abs(diff) / sum.previous_total) * 100);
    cmp += diff >= 0 ? `，比上月多 <span class="up">${pct}%</span>` : `，比上月少 <span class="down">${pct}%</span>`;
  }
  $("#monthCompare").innerHTML = cmp;
  renderDonut(sum.by_category, sum.total);
  renderBars(sum.daily);
  renderEntries($("#recentList"), list.slice(0, 8), "還沒有記錄");
  return list;
}

function renderFilterChips() {
  const all = [null, ...state.categories];
  $("#filterChips").innerHTML = all
    .map((c) => `<button class="chip ${state.filter === c ? "on" : ""}" data-cat="${esc(c ?? "")}">${c ? `<i style="background:${colorOf(c)}"></i>${esc(c)}` : "全部"}</button>`)
    .join("");
}

async function renderList() {
  renderFilterChips();
  const params = new URLSearchParams({ month: state.month });
  if (state.filter) params.set("category", state.filter);
  if (state.query) params.set("q", state.query);
  const list = await api(`/api/expenses?${params}`);
  renderEntries($("#fullList"), list, state.query || state.filter ? "找不到符合的記錄" : "這個月還沒有記錄");
  return list;
}

async function renderSettings() {
  $("#exportMonth").href = `/api/export.csv?month=${state.month}`;
  $("#categoryEditor").innerHTML = state.categories
    .map((c) => `<span class="chip"><i style="background:${colorOf(c)}"></i>${esc(c)}${c !== "其他" ? `<button type="button" data-del="${esc(c)}" aria-label="刪除">×</button>` : ""}</span>`)
    .join("");
  const st = await api("/api/status");
  const here = location.origin;
  const addrs = st.addresses.length ? st.addresses : [{ kind: "lan", url: here }];
  $("#addresses").innerHTML = addrs
    .map((a) => `<li><code>${esc(a.url)}</code><small>${a.kind === "tailscale" ? "出門也能用" : "同一個 Wi-Fi"}</small></li>`)
    .join("");
  const o = st.ollama;
  let html;
  if (o.model_ready) {
    html = `<div class="status-line"><span class="dot ok"></span>已啟用：${esc(o.model)}</div>
      <p class="muted small" style="margin-top:8px">沒有 QR code 的收據會交給它讀，結果會標「待確認」。</p>`;
  } else if (o.running) {
    html = `<div class="status-line"><span class="dot warn"></span>Ollama 已開啟，但還沒下載模型</div>
      <p class="muted small" style="margin-top:8px">在電腦的命令提示字元執行：</p><pre class="cmd">ollama pull ${esc(o.model)}</pre>`;
  } else {
    html = `<div class="status-line"><span class="dot"></span>未啟用（電子發票照常可以用）</div>
      <p class="muted small" style="margin-top:8px">想讓 AI 幫忙讀沒有 QR code 的收據、或自動填商家名稱，請在電腦安裝 Ollama（ollama.com），再執行：</p><pre class="cmd">ollama pull ${esc(o.model)}</pre>`;
  }
  $("#aiStatus").innerHTML = html;
  $("#dataDir").textContent = `資料存在電腦的：${st.data_dir}`;
}

async function refresh() {
  $("#monthLabel").textContent = monthLabel();
  try {
    let list = [];
    if (state.view === "home") list = await renderHome();
    else if (state.view === "list") list = await renderList();
    else await renderSettings();
    schedulePoll(list.some((e) => e.status === "processing"));
  } catch (err) {
    toast("連不到電腦：" + err.message);
  }
}

function schedulePoll(active) {
  clearTimeout(state.pollTimer);
  if (active) state.pollTimer = setTimeout(refresh, 2500);
}

async function loadCategories() {
  state.categories = await api("/api/categories");
}

// --- Upload -------------------------------------------------------------

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("讀不到照片")); };
    img.src = url;
  });
}

// Shrinking on the phone keeps uploads fast; 2400px still leaves the small QR codes sharp.
async function shrink(file, maxEdge = 2400) {
  try {
    const img = await loadImage(file);
    const scale = Math.min(1, maxEdge / Math.max(img.naturalWidth, img.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * scale);
    canvas.height = Math.round(img.naturalHeight * scale);
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    return await new Promise((r) => canvas.toBlob(r, "image/jpeg", 0.9));
  } catch {
    return file;
  }
}

async function uploadFiles(files) {
  if (!files.length) return;
  toast(files.length > 1 ? `上傳 ${files.length} 張照片…` : "上傳中…", 60000);
  let ok = 0;
  for (const file of files) {
    try {
      const blob = await shrink(file);
      const fd = new FormData();
      fd.append("file", blob, "receipt.jpg");
      await api("/api/receipts", { method: "POST", body: fd });
      ok++;
    } catch (err) {
      toast("上傳失敗：" + err.message);
    }
  }
  if (ok) toast(`已上傳 ${ok} 張，電腦正在辨識`);
  if (state.view === "settings") go("home"); else refresh();
}

// --- Edit sheet ---------------------------------------------------------

function renderCategoryPicker(selected) {
  $("#fCategory").innerHTML = state.categories
    .map((c) => `<button type="button" class="chip ${c === selected ? "on" : ""}" data-pick="${esc(c)}"><i style="background:${colorOf(c)}"></i>${esc(c)}</button>`)
    .join("");
}

function openSheet(e) {
  state.editing = e;
  const isNew = !e.id;
  $("#sheetTitle").textContent = isNew ? "手動記一筆" : e.status === "processing" ? "辨識中…" : "編輯記錄";
  $("#fAmount").value = e.amount ?? "";
  const unnamed = /^統編 /.test(e.merchant || "");
  $("#fMerchant").value = unnamed ? "" : e.merchant ?? "";
  $("#fMerchant").placeholder = unnamed ? `店名（${e.merchant}）` : "例如：全家便利商店";
  $("#fDate").value = e.date || localDate();
  $("#fNote").value = e.note ?? "";
  $("#fRemember").checked = true;
  state.pickedCategory = e.category || "其他";
  renderCategoryPicker(state.pickedCategory);

  const notice = $("#sheetNotice");
  notice.hidden = !e.message;
  notice.textContent = e.message || "";
  notice.classList.toggle("error", e.status === "error");

  const photo = $("#sheetPhoto");
  photo.hidden = !e.image;
  if (e.image) photo.querySelector("img").src = `/receipts/${e.thumb || e.image}`;

  const items = e.items || [];
  $("#itemsBox").hidden = !items.length;
  $("#itemsList").innerHTML = items
    .map((i) => `<li><span>${esc(i.name)}${i.qty !== 1 ? ` ×${i.qty}` : ""}</span><span>${money(i.qty * i.price)}</span></li>`)
    .join("");

  const meta = [];
  if (e.invoice_no) meta.push(`發票 ${e.invoice_no}`);
  if (e.seller_tax_id) meta.push(`統編 ${e.seller_tax_id}`);
  if (e.source) meta.push({ qr: "QR code 自動讀取", ai: "本機 AI 讀取", manual: "手動輸入", photo: "照片" }[e.source] || "");
  $("#sheetMeta").textContent = meta.filter(Boolean).join(" · ");

  $("#deleteBtn").hidden = isNew;
  $("#retryBtn").hidden = !e.image || e.status === "processing";
  $("#sheetBackdrop").hidden = false;
  $("#editSheet").hidden = false;
}

function closeSheet() {
  $("#sheetBackdrop").hidden = true;
  $("#editSheet").hidden = true;
  state.editing = null;
}

async function saveSheet(ev) {
  ev.preventDefault();
  const e = state.editing;
  const amount = parseFloat($("#fAmount").value);
  if (Number.isNaN(amount)) return toast("請輸入金額");
  const body = JSON.stringify({
    amount,
    merchant: $("#fMerchant").value.trim() || (/^統編 /.test(e.merchant || "") ? e.merchant : ""),
    date: $("#fDate").value,
    category: state.pickedCategory,
    note: $("#fNote").value.trim(),
    remember: $("#fRemember").checked,
  });
  try {
    if (e.id) await api(`/api/expenses/${e.id}`, { method: "PUT", body });
    else await api("/api/expenses", { method: "POST", body });
    closeSheet();
    toast("已儲存");
    refresh();
  } catch (err) {
    toast("儲存失敗：" + err.message);
  }
}

async function deleteCurrent() {
  const e = state.editing;
  if (!e?.id || !confirm("確定要刪除這筆記錄嗎？")) return;
  await api(`/api/expenses/${e.id}`, { method: "DELETE" });
  closeSheet();
  toast("已刪除");
  refresh();
}

async function retryCurrent() {
  const e = state.editing;
  await api(`/api/receipts/${e.id}/retry`, { method: "POST" });
  closeSheet();
  toast("重新辨識中");
  refresh();
}

// --- Wiring -------------------------------------------------------------

function bind() {
  $("#prevMonth").onclick = () => shiftMonth(-1);
  $("#nextMonth").onclick = () => shiftMonth(1);
  document.querySelectorAll("[data-goto]").forEach((b) => (b.onclick = () => go(b.dataset.goto)));
  $("#captureBtn").onclick = () => $("#fileInput").click();
  $("#fileInput").onchange = (ev) => {
    const files = [...ev.target.files];
    ev.target.value = "";
    uploadFiles(files);
  };
  $("#manualBtn").onclick = () => openSheet({ category: state.filter || "餐飲" });

  document.addEventListener("click", async (ev) => {
    const entry = ev.target.closest(".entry[data-id]");
    if (entry) {
      try { openSheet(await api(`/api/expenses/${entry.dataset.id}`)); } catch (err) { toast(err.message); }
      return;
    }
    const pick = ev.target.closest("[data-pick]");
    if (pick) {
      state.pickedCategory = pick.dataset.pick;
      renderCategoryPicker(state.pickedCategory);
      return;
    }
    const chip = ev.target.closest("#filterChips [data-cat]");
    if (chip) {
      state.filter = chip.dataset.cat || null;
      refresh();
      return;
    }
    const del = ev.target.closest("[data-del]");
    if (del && confirm(`刪除分類「${del.dataset.del}」？這個分類的記錄會改成「其他」。`)) {
      state.categories = await api(`/api/categories/${encodeURIComponent(del.dataset.del)}`, { method: "DELETE" });
      refresh();
    }
  });

  let searchTimer;
  $("#searchInput").oninput = (ev) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.query = ev.target.value.trim(); refresh(); }, 250);
  };

  $("#addCategoryForm").onsubmit = async (ev) => {
    ev.preventDefault();
    const name = $("#newCategory").value.trim();
    if (!name) return;
    try {
      state.categories = await api("/api/categories", { method: "POST", body: JSON.stringify({ name }) });
      $("#newCategory").value = "";
      refresh();
    } catch (err) { toast(err.message); }
  };

  $("#editSheet").onsubmit = saveSheet;
  $("#closeSheet").onclick = closeSheet;
  $("#sheetBackdrop").onclick = closeSheet;
  $("#deleteBtn").onclick = deleteCurrent;
  $("#retryBtn").onclick = retryCurrent;
  $("#sheetPhoto").onclick = () => {
    const e = state.editing;
    if (!e?.image) return;
    $("#viewer img").src = `/receipts/${e.image}`;
    $("#viewer").hidden = false;
  };
  $("#viewer").onclick = () => ($("#viewer").hidden = true);

  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
}

(async function init() {
  bind();
  try { await loadCategories(); } catch (err) { toast("連不到電腦：" + err.message); }
  refresh();
})();
