"use strict";
// Presenter panel: speaker notes + section timers + optional AI helper.
// Talks only to panel_server.py on 127.0.0.1.
const $ = (s) => document.querySelector(s);
const LS = {
  get(k, d) { try { const v = localStorage.getItem("presenter." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("presenter." + k, JSON.stringify(v)); } catch {} },
};
const post = (url, body) => fetch(url, {
  method: "POST", headers: { "Content-Type": "application/json", "X-Panel": "1" }, body: JSON.stringify(body || {}),
});

// ------------------------------------------------------------ i18n
const I18N = {
  en: {
    "mirror.tip": "Projector status (reported by mirror.py)", "font.down": "Smaller text", "font.up": "Larger text",
    "src.label": "Projecting: ", "timer.total": "Total", "timer.start": "▶ Start", "timer.next": "Next ⏭",
    "timer.reset": "Reset all timers", "timer.notStarted": "Not started",
    "timer.hint": "Press Start to begin timing; click a section above to jump.",
    "timer.confirmJump": "Switch the timer to “{s}” and start from 0?", "timer.confirmReset": "Reset all timers?",
    "tab.notes": "Notes", "tab.ai": "AI helper", "follow.tip": "Jump to the matching notes section when the projected page changes",
    "follow.on": "Auto-follow: on", "follow.off": "Auto-follow: off", "nav.prev": "Previous section (← / PgUp)",
    "nav.next": "Next section (→ / PgDn)", "notes.opening": "(opening)", "notes.cannotRead": "Cannot load notes: ",
    "notes.followed": "Notes followed to: {sec} (by {by}: {title})", "by.title": "title", "by.url": "URL",
    "stage.hint": "This section is “{v}”; the timer is on “{c}”.", "stage.switch": "Time {v}",
    "mirror.offline": "Projector: not connected", "mirror.blank": "Projector: blank screen", "mirror.frozen": "Projector: frozen",
    "mirror.live": "Projector: live {fps} fps · {style}", "style.ring": "ring", "style.spotlight": "spotlight",
    "mirror.unclipped": " · mouse unlocked", "server.offline": "Panel server not connected",
    "src.none": "(none: click the window to project and press {pick})", "src.popup": "Popup (auto): {t}",
    "src.noPopups": "  (popups not followed)", "hotkeys.failed": "Hotkeys taken by another program: {k}. Change them in config.json.",
    "reload.later": "Panel updated: press F5 after your AI conversation", "ai.placeholder": "Ask about your notes or materials…",
    "ai.withStage": "Include current section", "ai.new": "New chat", "ai.newTip": "Clear the conversation",
    "ai.stop": "Stop", "ai.send": "Send", "ai.intro": "Read-only assistant: it can read files under the configured folder, cannot edit files or run commands, and is blocked from .env and key files. <kbd>Enter</kbd> sends, <kbd>Shift</kbd>+<kbd>Enter</kbd> adds a line.",
    "ai.disabled": "The AI helper is off. To enable it set <code>\"ai_helper\": {\"enabled\": true}</code> in <code>config.json</code> and restart (see README).",
    "ai.thinking": "Sent, thinking…", "ai.resumed": " (continuing conversation)", "ai.answering": "Answering…",
    "ai.reading": "Reading: ", "ai.denied": "⚠ Tool blocked: ", "ai.noAnswer": "(no answer)", "ai.hadError": " · had errors",
    "ai.stopped": "Stopped.", "ai.error": "Error: ", "ai.newDone": "New conversation started.", "ai.secs": "{n} s",
    "step.prev": "Previous step (↑ / K)", "step.next": "Next step (↓ / J)", "step.tip": "Steps in this section",
    "step.label": "{t} ({i}/{n})",
    "keys.tip": "Keyboard shortcuts (?)", "keys.title": "⌨ Keyboard shortcuts", "keys.close": "Close (Esc or ?)",
    "keys.global": "Global (work in any window)", "keys.panel": "Panel (click the panel first)",
    "keys.failed": " ⚠ taken by another program: change it in config.json",
    "hk.pick": "Project the current foreground window", "hk.bring": "Move the source window next to the panel",
    "hk.freeze": "Freeze / unfreeze the projector (before typing anything private)",
    "hk.blank": "Blank “Please wait” screen / back", "hk.style": "Pointer style: ring ↔ spotlight",
    "hk.next": "Next notes section, from any window", "hk.prev": "Previous notes section, from any window",
    "hk.popups": "Follow popups: on / off", "hk.clip": "Confine the mouse to the presenter display: on / off",
    "hk.quit": "Quit the mirror (the panel stays open)",
    "pk.section": "Previous / next section", "pk.step": "Previous / next step (no steps: scroll)",
    "pk.home": "First section", "pk.keys": "Show / hide this list", "pk.reload": "Reload the panel (after editing notes or config)",
  },
  "zh-TW": {
    "mirror.tip": "投影狀態（mirror.py 回報）", "font.down": "字小一點", "font.up": "字大一點",
    "src.label": "投影來源：", "timer.total": "全場", "timer.start": "▶ 開始", "timer.next": "下一段 ⏭",
    "timer.reset": "重設所有計時", "timer.notStarted": "尚未開始",
    "timer.hint": "按「開始」開始計時；點上面的段落可以跳段。",
    "timer.confirmJump": "把計時切到「{s}」並從 0 開始？", "timer.confirmReset": "重設所有計時？",
    "tab.notes": "講稿", "tab.ai": "AI 助手", "follow.tip": "投影的頁面換了，講稿自動跳到對應的段落",
    "follow.on": "講稿自動跟隨：開", "follow.off": "講稿自動跟隨：關", "nav.prev": "上一節（← / PgUp）",
    "nav.next": "下一節（→ / PgDn）", "notes.opening": "（開頭）", "notes.cannotRead": "讀不到講稿：",
    "notes.followed": "講稿已跟著切到：{sec}（依{by}：{title}）", "by.title": "標題", "by.url": "網址",
    "stage.hint": "這一節是「{v}」，計時目前在「{c}」。", "stage.switch": "切到 {v} 計時",
    "mirror.offline": "投影：未連線", "mirror.blank": "投影：請稍候畫面", "mirror.frozen": "投影：已凍結",
    "mirror.live": "投影：即時 {fps}fps · {style}", "style.ring": "光圈", "style.spotlight": "聚光燈",
    "mirror.unclipped": " · 滑鼠未鎖", "server.offline": "面板伺服器未連線",
    "src.none": "（未指定，請點要投影的視窗再按 {pick}）", "src.popup": "彈窗（自動）：{t}",
    "src.noPopups": "　（不跟隨彈窗）", "hotkeys.failed": "這些熱鍵被其他程式佔用：{k}，請在 config.json 改掉。",
    "reload.later": "面板程式已更新：問完 AI 後按 F5 重新載入", "ai.placeholder": "問講稿或教材的問題…",
    "ai.withStage": "附上目前段落", "ai.new": "新對話", "ai.newTip": "清掉對話，下一題重新開始",
    "ai.stop": "停止", "ai.send": "送出", "ai.intro": "唯讀助手：只能讀設定資料夾裡的檔案，不能改檔、不能執行指令，也讀不到 .env 和金鑰檔。按 <kbd>Enter</kbd> 送出，<kbd>Shift</kbd>+<kbd>Enter</kbd> 換行。",
    "ai.disabled": "AI 助手未啟用。要啟用請在 <code>config.json</code> 設定 <code>\"ai_helper\": {\"enabled\": true}</code> 並重新啟動（見 README）。",
    "ai.thinking": "已送出，思考中…", "ai.resumed": "（延續對話）", "ai.answering": "回答中…",
    "ai.reading": "查資料：", "ai.denied": "⚠ 工具被拒：", "ai.noAnswer": "（沒有回答）", "ai.hadError": " · 有錯誤",
    "ai.stopped": "已停止。", "ai.error": "錯誤：", "ai.newDone": "已開新對話。", "ai.secs": "{n} 秒",
    "step.prev": "上一步（↑ / K）", "step.next": "下一步（↓ / J）", "step.tip": "這一節的步驟",
    "step.label": "{t}（{i}/{n}）",
    "keys.tip": "快捷鍵一覽（?）", "keys.title": "⌨ 快捷鍵一覽", "keys.close": "關閉（Esc 或 ?）",
    "keys.global": "全域（任何視窗都有效）", "keys.panel": "面板（先點一下面板）",
    "keys.failed": " ⚠ 被其他程式佔用：請在 config.json 改掉",
    "hk.pick": "把目前前景視窗設為投影來源", "hk.bring": "把來源視窗搬回筆電螢幕、放在面板旁邊",
    "hk.freeze": "凍結／解凍投影（輸入私人資料前先按）",
    "hk.blank": "「請稍候」畫面／切回", "hk.style": "游標樣式：光圈 ↔ 聚光燈",
    "hk.next": "講稿下一節（不用切到面板）", "hk.prev": "講稿上一節（不用切到面板）",
    "hk.popups": "自動跟隨彈窗：開／關", "hk.clip": "滑鼠鎖在講者螢幕：開／關",
    "hk.quit": "結束投影（面板留著）",
    "pk.section": "上一節／下一節", "pk.step": "這一節的上一步／下一步（沒有步驟時：捲動）",
    "pk.home": "回到第一節", "pk.keys": "開／關這張快捷鍵表", "pk.reload": "重新載入面板（改了講稿或設定後）",
  },
};
let LANG = "en", CONF = { hotkeys: {}, ai_helper: false };
function T(key, vars) {
  let s = (I18N[LANG] && I18N[LANG][key]) ?? I18N.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split("{" + k + "}").join(String(v));
  return s;
}
function applyI18n() {
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = T(el.dataset.i18n)));
  document.querySelectorAll("[data-i18n-title]").forEach((el) => (el.title = T(el.dataset.i18nTitle)));
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => (el.placeholder = T(el.dataset.i18nPlaceholder)));
  $("#aiIntro").innerHTML = CONF.ai_helper ? T("ai.intro") : T("ai.disabled");
  $("#askForm").hidden = !CONF.ai_helper;
  $("#tabAi").classList.toggle("off", !CONF.ai_helper);
  $("#mirror").textContent = T("mirror.offline");
}
const key = (action) => (CONF.hotkeys && CONF.hotkeys[action]) || "?";

// ------------------------------------------------------------ mini Markdown
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
function inline(s) {
  const codes = [];
  s = esc(s).replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return "\u0000" + (codes.length - 1) + "\u0000"; });
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
       .replace(/(^|[^*])\*([^*\s][^*]*?)\*/g, "$1<em>$2</em>")
       .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, u) => /^https?:\/\//.test(u) ? `<a href="${u}" target="_blank" rel="noopener">${t}</a>` : `<span title="${u}"><u>${t}</u></span>`);
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[+i]}</code>`);
}
function md(src) {
  const lines = src.replace(/\r/g, "").split("\n");
  let out = [], i = 0;
  const listStack = [];
  const closeLists = (depth = 0) => { while (listStack.length > depth) out.push(`</${listStack.pop()}>`); };
  while (i < lines.length) {
    let ln = lines[i];
    if (/^```/.test(ln)) {
      closeLists(); const buf = []; i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      i++; out.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`); continue;
    }
    if (/^\s*$/.test(ln)) { closeLists(); i++; continue; }
    let m;
    if ((m = ln.match(/^(#{1,6})\s+(.*)/))) { closeLists(); out.push(`<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`); i++; continue; }
    if (/^(-{3,}|\*{3,})\s*$/.test(ln)) { closeLists(); out.push("<hr>"); i++; continue; }
    if (/^\s*>/.test(ln)) {
      closeLists(); const buf = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
      out.push(`<blockquote>${md(buf.join("\n"))}</blockquote>`); continue;
    }
    if (/^\s*\|/.test(ln) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      closeLists();
      const row = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim()));
      const head = row(ln); i += 2; const body = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) body.push(row(lines[i++]));
      out.push("<table><thead><tr>" + head.map((c) => `<th>${c}</th>`).join("") + "</tr></thead><tbody>" +
        body.map((r) => "<tr>" + r.map((c) => `<td>${c}</td>`).join("") + "</tr>").join("") + "</tbody></table>");
      continue;
    }
    if ((m = ln.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)/))) {
      const depth = Math.floor(m[1].replace(/\t/g, "  ").length / 2) + 1;
      const tag = /\d/.test(m[2]) ? "ol" : "ul";
      while (listStack.length < depth) { listStack.push(tag); out.push(`<${tag}>`); }
      closeLists(depth);
      let text = m[3], cls = "";
      const t = text.match(/^\[( |x|X)\]\s+(.*)/);
      if (t) { cls = ' class="task"'; text = (t[1] === " " ? "☐ " : "☑ ") + t[2]; }
      i++;  // continuation lines (indented, not a new item)
      while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) text += " " + lines[i++].trim();
      out.push(`<li${cls}>${inline(text)}</li>`); continue;
    }
    closeLists();
    const buf = [ln]; i++;
    while (i < lines.length && !/^\s*$/.test(lines[i]) && !/^(#|```|\s*>|\s*[-*+]\s|\s*\d+[.)]\s|\s*\|)/.test(lines[i])) buf.push(lines[i++]);
    out.push(`<p>${buf.map(inline).join("<br>")}</p>`);
  }
  closeLists();
  return out.join("\n");
}

// ------------------------------------------------------------ font size
let fs = LS.get("fs", 20);
const applyFs = () => document.documentElement.style.setProperty("--fs", fs + "px");
applyFs();
$("#fontUp").onclick = () => { fs = Math.min(34, fs + 1); LS.set("fs", fs); applyFs(); };
$("#fontDown").onclick = () => { fs = Math.max(13, fs - 1); LS.set("fs", fs); applyFs(); };

// ------------------------------------------------------------ tabs
function showTab(name) {
  if (!["notes", "ai"].includes(name)) name = "notes";
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-" + name));
  LS.set("tab", name);
  if (name === "ai" && CONF.ai_helper) $("#q").focus();
}
document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));

// ------------------------------------------------------------ timers (sections come from the pacing file)
let stages = [];
let timer = LS.get("timer", { cur: -1, starts: {}, classStart: null });
const saveTimer = () => LS.set("timer", timer);
const mmss = (ms) => {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : String(m).padStart(2, "0")) + ":" + String(r).padStart(2, "0");
};
function startStage(idx) {
  if (idx < 0 || idx >= stages.length) return;
  const now = Date.now();
  if (!timer.classStart) timer.classStart = now;
  timer.cur = idx; timer.starts[stages[idx].key] = now; saveTimer(); renderStages(); tick();
}
function renderStages() {
  const box = $("#stages"); box.innerHTML = "";
  stages.forEach((s, i) => {
    const b = document.createElement("button");
    b.textContent = s.short;
    b.title = `${s.short}${s.title ? " — " + s.title : ""} (${s.minutes} min)`;
    if (i === timer.cur) b.classList.add("cur"); else if (i < timer.cur) b.classList.add("done");
    if (i === viewStage) b.classList.add("view");
    b.onclick = () => { if (i !== timer.cur && confirm(T("timer.confirmJump", { s: s.short }))) startStage(i); };
    box.appendChild(b);
  });
  $("#btnStart").hidden = timer.cur >= 0 || !stages.length;
  $("#btnNext").hidden = timer.cur < 0 || timer.cur >= stages.length - 1;
  const s = stages[timer.cur];
  $("#stageName").textContent = s ? `${s.short}${s.title ? "　" + s.title : ""}` : T("timer.notStarted");
  $("#stageDetail").textContent = s ? s.detail : (stages.length ? T("timer.hint") : "");
}
function tick() {
  $("#clock").textContent = new Date().toTimeString().slice(0, 8);
  const s = stages[timer.cur];
  const el = $("#stageTime"), bar = $("#stageBar");
  if (s) {
    const ms = Date.now() - (timer.starts[s.key] || Date.now()), plan = s.minutes * 60000, r = ms / plan;
    el.textContent = `${mmss(ms)} / ${mmss(plan)}`;
    const cls = r >= 1 ? "over" : r >= 0.8 ? "warn" : "";
    el.className = "mono " + cls; bar.className = cls; bar.style.width = Math.min(100, r * 100) + "%";
  } else { el.textContent = "00:00 / 00:00"; el.className = "mono"; bar.style.width = "0"; }
  $("#classTime").textContent = timer.classStart ? mmss(Date.now() - timer.classStart) : "00:00";
}
$("#btnStart").onclick = () => startStage(0);
$("#btnNext").onclick = () => startStage(timer.cur + 1);
$("#btnResetTimer").onclick = () => {
  if (confirm(T("timer.confirmReset"))) { timer = { cur: -1, starts: {}, classStart: null }; saveTimer(); renderStages(); tick(); }
};
setInterval(tick, 500);

// ------------------------------------------------------------ notes
let docs = [], docIdx = LS.get("doc", 0), sections = [], secIdx = 0, viewStage = -1;
function splitSections(text) {
  const lines = text.replace(/\r/g, "").split("\n"), secs = [];
  let cur = { title: "", lines: [] }, inFence = false;
  for (const ln of lines) {
    if (/^```/.test(ln)) inFence = !inFence;
    if (!inFence && /^##\s/.test(ln)) { if (cur.lines.join("").trim()) secs.push(cur); cur = { title: ln.replace(/^##\s+/, ""), lines: [ln] }; }
    else { if (!cur.title && /^#\s/.test(ln)) cur.title = ln.replace(/^#\s+/, ""); cur.lines.push(ln); }
  }
  if (cur.lines.join("").trim()) secs.push(cur);
  return secs.map((s) => ({ title: s.title || T("notes.opening"), text: s.lines.join("\n") }));
}
// Same rule as presenter_sidecar.notes.stage_for_heading: the longest pacing name found in the heading.
function stageOfTitle(t) {
  const h = t.toLowerCase(); let best = -1, len = 0;
  stages.forEach((s, i) => { const n = s.short.toLowerCase(); if (n && h.includes(n) && n.length > len) { best = i; len = n.length; } });
  return best;
}
function renderDocBar() {
  const box = $("#docs"); box.innerHTML = "";
  docs.forEach((d, i) => {
    const b = document.createElement("button");
    b.textContent = d.name.replace(/\.md$/, ""); b.title = d.path;
    if (i === docIdx) b.classList.add("active");
    b.onclick = () => openDoc(i, 0);
    box.appendChild(b);
  });
}
function openDoc(i, sec) {
  docIdx = Math.max(0, Math.min(docs.length - 1, i)); LS.set("doc", docIdx);
  sections = splitSections(docs[docIdx].text);
  const sel = $("#secSel"); sel.innerHTML = "";
  sections.forEach((s, k) => { const o = document.createElement("option"); o.value = k; o.textContent = `${k + 1}/${sections.length}　${s.title}`; sel.appendChild(o); });
  // sec == null: first load or reload, so return to the last section AND step; otherwise start at step 1.
  renderDocBar(); goSection(sec == null ? LS.get("sec." + docIdx, 0) : sec, sec == null);
}
function goSection(k, restoreStep = false) {
  if (!sections.length) return;
  secIdx = Math.max(0, Math.min(sections.length - 1, k)); LS.set("sec." + docIdx, secIdx);
  $("#secSel").value = secIdx;
  const art = $("#note"); art.innerHTML = md(sections[secIdx].text); art.scrollTop = 0;
  buildSteps();
  if (steps.length) {
    const saved = restoreStep ? LS.get(stepKey(), 0) : 0;
    if (saved > 0) goStep(saved); else goStep(0, false);  // new section: step 1, scrolled to the top
  }
  viewStage = stageOfTitle(sections[secIdx].title);
  post("/api/panel", { doc: docs[docIdx].name, section: sections[secIdx].title, index: `${secIdx + 1}/${sections.length}`, follow: notesFollow }).catch(() => {});
  const hint = $("#stageHint");
  if (viewStage >= 0 && viewStage !== timer.cur) {
    const v = esc(stages[viewStage].short), c = esc(stages[timer.cur]?.short || T("timer.notStarted"));
    hint.hidden = false;
    hint.innerHTML = `${T("stage.hint", { v, c })} <button id="syncStage">${T("stage.switch", { v })}</button>`;
    $("#syncStage").onclick = () => { startStage(viewStage); hint.hidden = true; };
  } else hint.hidden = true;
  renderStages();
}
$("#secSel").onchange = (e) => goSection(+e.target.value);
$("#prev").onclick = () => goSection(secIdx - 1);
$("#next").onclick = () => goSection(secIdx + 1);

// ------------------------------------------------------------ steps inside a section
// Same rule as presenter_sidecar.notes.section_steps: a step is a paragraph whose only content is a
// bold numbered title "**N. title**"; sections without any use their ### headings instead.
// Each step (title + following blocks up to the next step, heading, rule or quote) is wrapped in
// <div class="step"> so it can be highlighted and scrolled to.
let steps = [], stepIdx = 0, spyRaf = 0;
const stepKey = () => `step.${docs[docIdx]?.name}.${sections[secIdx]?.title}`;
function boldStepTitle(el) {
  if (el.tagName !== "P" || el.children.length !== 1 || el.firstElementChild.tagName !== "STRONG") return null;
  if (el.textContent.trim() !== el.firstElementChild.textContent.trim()) return null;
  const t = el.textContent.trim();
  return /^\d+[.．]\s*\S/.test(t) ? t : null;  // keep the number as written in the notes
}
function buildSteps() {
  const art = $("#note"), kids = [...art.children];
  let heads = kids.filter((el) => boldStepTitle(el) != null), bold = true;
  if (!heads.length) { heads = kids.filter((el) => el.tagName === "H3"); bold = false; }
  const isHead = new Set(heads);
  const ends = (el) => isHead.has(el) || el.tagName === "HR" ||
    (bold ? /^H[1-6]$/.test(el.tagName) || el.tagName === "BLOCKQUOTE" : /^H[1-3]$/.test(el.tagName));
  steps = heads.map((h) => {
    const box = document.createElement("div"); box.className = "step";
    h.before(box);
    let el = h;
    do { const nx = el.nextElementSibling; box.appendChild(el); el = nx; } while (el && !ends(el));
    return { el: box, title: bold ? boldStepTitle(h) : h.textContent.trim() };
  });
  stepIdx = 0;
  const sel = $("#stepSel"); sel.innerHTML = "";
  steps.forEach((s, i) => {
    const o = document.createElement("option"); o.value = i;
    o.textContent = T("step.label", { t: s.title, i: i + 1, n: steps.length }); sel.appendChild(o);
  });
  $("#stepnav").hidden = !steps.length;
}
function stickyOffset(art) {  // sticky headers inside the notes scroller cover the top: scroll below them
  let h = 0;
  for (const el of art.children) if (getComputedStyle(el).position === "sticky") h = Math.max(h, el.offsetHeight);
  return h;
}
function goStep(k, scroll = true) {
  if (!steps.length) return;
  stepIdx = Math.max(0, Math.min(steps.length - 1, k));
  $("#stepSel").value = stepIdx;
  steps.forEach((s, i) => s.el.classList.toggle("hl", i === stepIdx));
  LS.set(stepKey(), stepIdx);
  if (scroll) {
    const art = $("#note");
    art.scrollTop += steps[stepIdx].el.getBoundingClientRect().top - art.getBoundingClientRect().top - stickyOffset(art) - 4;
  }
}
function spyStep() {  // manual scrolling: the drop-down follows the step nearest the top
  spyRaf = 0;
  if (!steps.length) return;
  const art = $("#note"), top = art.getBoundingClientRect().top, line = top + stickyOffset(art) + 48;
  let k = 0;
  for (let i = 0; i < steps.length; i++) { if (steps[i].el.getBoundingClientRect().top <= line) k = i; else break; }
  // At the bottom the last steps cannot reach the top: keep a selected step that is still in view.
  const atEnd = art.scrollTop + art.clientHeight >= art.scrollHeight - 2;
  const cur = steps[stepIdx].el.getBoundingClientRect();
  if (atEnd && k < stepIdx && cur.top < top + art.clientHeight && cur.bottom > top) return;
  if (k !== stepIdx) goStep(k, false);
}
$("#note").addEventListener("scroll", () => { if (!spyRaf) spyRaf = requestAnimationFrame(spyStep); }, { passive: true });
$("#stepSel").onchange = (e) => { goStep(+e.target.value); e.target.blur(); };  // blur: ↑/↓ and J/K work right away
$("#stepPrev").onclick = () => goStep(stepIdx - 1);
$("#stepNext").onclick = () => goStep(stepIdx + 1);
function stepBy(d) {
  if (!steps.length) { $("#note").scrollBy(0, d * 120); return; }  // no steps in this section: scroll
  if (d < 0 && stepIdx === 0) { $("#note").scrollTop = 0; return; } // up from step 1: back to the section top
  goStep(stepIdx + d);
}

const typing = () => /TEXTAREA|INPUT|SELECT/.test(document.activeElement?.tagName || "") || document.activeElement?.isContentEditable;
document.addEventListener("keydown", (e) => {
  if (typing() || !$("#keysOverlay").hidden) return;
  if (!$("#tab-notes").classList.contains("active")) return;
  if (e.ctrlKey || e.altKey || e.metaKey) return;  // leave Ctrl+Alt+PgUp/PgDn and browser shortcuts alone
  if (e.key === "PageDown" || e.key === "ArrowRight") { goSection(secIdx + 1); e.preventDefault(); }
  else if (e.key === "PageUp" || e.key === "ArrowLeft") { goSection(secIdx - 1); e.preventDefault(); }
  else if (e.key === "Home") { goSection(0); e.preventDefault(); }
  else if (e.key === "ArrowDown" || e.key === "j" || e.key === "J") { stepBy(1); e.preventDefault(); }
  else if (e.key === "ArrowUp" || e.key === "k" || e.key === "K") { stepBy(-1); e.preventDefault(); }
});

// ------------------------------------------------------------ ⌨ keyboard shortcuts overlay
// Global hotkeys come from the configured `hotkeys` map (empty = disabled), so the list always
// matches config.json; keys mirror.py could not register are flagged.
let hotkeysFailed = [];
const kbds = (spec) => String(spec).split("+").map((k) => `<kbd>${esc(k.trim())}</kbd>`).join("+");
const keyRow = (keysHtml, desc, cls = "") => `<tr${cls ? ` class="${cls}"` : ""}><td>${keysHtml}</td><td>${desc}</td></tr>`;
function renderKeys() {
  const hk = CONF.hotkeys || {};
  $("#keysGlobal").innerHTML = Object.entries(hk).filter(([, spec]) => spec).map(([action, spec]) => {
    const failed = hotkeysFailed.includes(action);
    const label = T("hk." + action) === "hk." + action ? action : T("hk." + action);
    return keyRow(kbds(spec), esc(label) + ` <span class="muted">(<code>${esc(action)}</code>)</span>` +
      (failed ? esc(T("keys.failed")) : ""), failed ? "failed" : "");
  }).join("");
  const or = (a, b) => `${kbds(a)} / ${kbds(b)}`;
  $("#keysPanel").innerHTML = [
    keyRow(`${or("←", "→")}, ${or("PgUp", "PgDn")}`, esc(T("pk.section"))),
    keyRow(`${or("↑", "↓")}, ${or("K", "J")}`, esc(T("pk.step"))),
    keyRow(kbds("Home"), esc(T("pk.home"))),
    keyRow(`${kbds("?")}, ${kbds("Esc")}`, esc(T("pk.keys"))),
    keyRow(kbds("F5"), esc(T("pk.reload"))),
  ].join("");
}
function toggleKeys(show) {
  const o = $("#keysOverlay"), open = show === undefined ? o.hidden : show;
  if (open === !o.hidden) return;
  o.hidden = !open;
  (open ? $("#keysClose") : $("#keysBtn")).focus();
}
$("#keysBtn").onclick = () => toggleKeys();
$("#keysClose").onclick = () => toggleKeys(false);
document.addEventListener("keydown", (e) => {
  if (typing() || e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.key === "?") { toggleKeys(); e.preventDefault(); e.stopImmediatePropagation(); }
  else if (e.key === "Escape" && !$("#keysOverlay").hidden) { toggleKeys(false); e.preventDefault(); e.stopImmediatePropagation(); }
}, true);

// ------------------------------------------------------------ notes auto-follow
// Jumps only when the projected page maps to a DIFFERENT section; manual paging is never overridden.
let notesFollow = null, lastNotesKey, webVersion = null, toastTimer = null;
function toast(msg, ms = 4000) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); if (ms) toastTimer = setTimeout(() => (t.hidden = true), ms);
}
function renderFollowBtn() {
  const b = $("#followBtn"); b.textContent = T(notesFollow ? "follow.on" : "follow.off"); b.classList.toggle("on", !!notesFollow);
}
$("#followBtn").onclick = () => { notesFollow = !notesFollow; LS.set("notesFollow", notesFollow); renderFollowBtn(); };
function followTo(nt) {
  let di = nt.doc ? docs.findIndex((d) => d.name === nt.doc || d.path.endsWith(nt.doc)) : docIdx;
  if (di < 0) di = docIdx;
  const secs = splitSections(docs[di].text);
  const k = secs.findIndex((x) => x.title.includes(nt.section));
  if (k < 0) return;
  if (di !== docIdx) openDoc(di, k); else goSection(k);
  toast(T("notes.followed", { sec: secs[k].title, by: T("by." + nt.by), title: nt.title }));
}
function handleNotesTarget(st) {
  if (notesFollow === null) { notesFollow = LS.get("notesFollow", st.notes_auto_follow_default !== false); renderFollowBtn(); }
  const nt = st.notes_target;
  if (!nt || !nt.key || !docs.length) return;                         // no rule matched: stay
  if (lastNotesKey === undefined) { lastNotesKey = nt.key; return; }  // panel just opened: keep your place
  if (nt.key === lastNotesKey) return;                                // same section: do not move
  lastNotesKey = nt.key;
  if (notesFollow) followTo(nt);
}
function handleVersion(st) {
  if (!st.web_version) return;
  if (webVersion === null) { webVersion = st.web_version; return; }
  if (st.web_version === webVersion) return;
  webVersion = st.web_version;
  const chatting = aborter || chat.querySelectorAll(".msg.user").length > 0;
  if (!chatting) location.reload(); else toast(T("reload.later"), 0);
}

// ------------------------------------------------------------ projector status + global paging hotkeys
let lastCmdSeq = null;
async function pollState() {
  try {
    const st = await (await fetch("/api/state")).json();
    const pill = $("#mirror"), m = st.mirror || {};
    const stale = st.mirror_age == null || st.mirror_age > 4;
    pill.className = "pill";
    if (stale) pill.textContent = T("mirror.offline");
    else if (m.blank) { pill.textContent = T("mirror.blank") + ` (${key("blank")})`; pill.classList.add("blank"); }
    else if (m.frozen) { pill.textContent = T("mirror.frozen") + ` (${key("freeze")})`; pill.classList.add("frozen"); }
    else {
      pill.textContent = T("mirror.live", { fps: m.fps ?? "?", style: T(m.style === "spotlight" ? "style.spotlight" : "style.ring") }) + (m.clip === false ? T("mirror.unclipped") : "");
      pill.classList.add("live");
    }
    // The source title is shown only here, never on the projector.
    const srcName = m.following_popup ? T("src.popup", { t: m.popup_title }) : (m.source_title || T("src.none", { pick: key("pick") }));
    $("#srcTitle").textContent = stale ? "—" : srcName + (m.backend && m.backend !== "-" ? `  [${m.backend}]` : "") + (m.follow_popups === false ? T("src.noPopups") : "");
    $("#srcTitle").classList.toggle("popup", !!m.following_popup);
    const warn = $("#srcWarn");
    const failedNow = stale ? [] : (m.hotkeys_failed || []);
    if (failedNow.join() !== hotkeysFailed.join()) { hotkeysFailed = failedNow; renderKeys(); }
    const failed = failedNow.length ? T("hotkeys.failed", { k: failedNow.join(", ") }) : "";
    const w = stale ? "" : (m.warning || failed || m.notice || "");  // warnings win over notices
    warn.hidden = !w; warn.textContent = w;
    warn.className = "srcwarn small" + (!m.warning && !failed && m.notice ? " info" : "");
    handleNotesTarget(st); handleVersion(st);
    const cmds = st.cmds || [];
    if (lastCmdSeq == null) lastCmdSeq = cmds.length ? cmds[cmds.length - 1].seq : 0;
    for (const c of cmds) if (c.seq > lastCmdSeq) {
      lastCmdSeq = c.seq;
      if (c.nav) { showTab("notes"); goSection(secIdx + c.nav); }
    }
  } catch { $("#mirror").textContent = T("server.offline"); $("#mirror").className = "pill blank"; }
}
setInterval(pollState, 700);

// ------------------------------------------------------------ AI helper (optional, read-only)
const chat = $("#chat");
function addMsg(cls, html) {
  const d = document.createElement("div"); d.className = "msg " + cls; d.innerHTML = html; chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight; return d;
}
let aborter = null;
async function ask(q) {
  addMsg("user", esc(q));
  const bot = addMsg("bot md", '<span class="muted">…</span>');
  const prog = $("#progress"); prog.hidden = false;
  $("#btnSend").disabled = true; $("#btnStop").hidden = false;
  const t0 = Date.now(); let status = T("ai.thinking"), text = "";
  const timerId = setInterval(() => { prog.textContent = `⏳ ${T("ai.secs", { n: Math.round((Date.now() - t0) / 1000) })} · ${status}`; }, 250);
  const s = stages[timer.cur];
  const context = $("#withStage").checked && s ? `${s.short} ${s.title}`.trim() : "";
  aborter = new AbortController();
  try {
    const res = await fetch("/api/ask", {
      method: "POST", signal: aborter.signal,
      headers: { "Content-Type": "application/json", "X-Panel": "1" }, body: JSON.stringify({ q, context }),
    });
    if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.error || res.statusText); }
    const reader = res.body.getReader(), dec = new TextDecoder(); let buf = "";
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
        if (!line.trim()) continue;
        const ev = JSON.parse(line);
        if (ev.t === "status") status = ev.msg + (ev.resume ? T("ai.resumed") : "");
        else if (ev.t === "turn") { if (text && !text.endsWith("\n\n")) text += "\n\n"; }
        else if (ev.t === "delta") { text += ev.text; bot.innerHTML = md(text); status = T("ai.answering"); chat.scrollTop = chat.scrollHeight; }
        else if (ev.t === "tool") status = T("ai.reading") + `${ev.name} ${ev.target}`;
        else if (ev.t === "tool_denied") status = T("ai.denied") + ev.msg;
        else if (ev.t === "done") {
          bot.innerHTML = md(ev.text || text || T("ai.noAnswer")) +
            `<div class="meta">${T("ai.secs", { n: ev.secs })}${ev.cost != null ? " · $" + Number(ev.cost).toFixed(3) : ""}${ev.is_error ? T("ai.hadError") : ""}</div>`;
        } else if (ev.t === "error") addMsg("err", esc(ev.msg));
      }
    }
  } catch (e) {
    if (e.name === "AbortError") addMsg("err", T("ai.stopped")); else addMsg("err", T("ai.error") + esc(String(e.message || e)));
    if (bot.textContent === "…") bot.remove();
  } finally {
    clearInterval(timerId); prog.hidden = true; aborter = null;
    $("#btnSend").disabled = false; $("#btnStop").hidden = true; chat.scrollTop = chat.scrollHeight;
  }
}
$("#askForm").onsubmit = (e) => { e.preventDefault(); const q = $("#q").value.trim(); if (!q || aborter || !CONF.ai_helper) return; $("#q").value = ""; ask(q); };
$("#q").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("#askForm").requestSubmit(); } });
$("#btnStop").onclick = async () => { await post("/api/cancel"); aborter?.abort(); };
$("#btnNew").onclick = async () => { await post("/api/reset"); chat.querySelectorAll(".msg:not(.sys)").forEach((m) => m.remove()); addMsg("sys", T("ai.newDone")); };

// ------------------------------------------------------------ start
(async function init() {
  try { CONF = await (await fetch("/api/config")).json(); LANG = I18N[CONF.ui_lang] ? CONF.ui_lang : "en"; } catch {}
  applyI18n(); renderKeys();
  try {
    stages = (await (await fetch("/api/pacing")).json()).stages || [];
    if (timer.cur >= stages.length) timer.cur = -1;
    docs = (await (await fetch("/api/notes")).json()).docs || [];
    if (docs.length) openDoc(Math.min(docIdx, docs.length - 1), null);
  } catch (e) { $("#note").textContent = T("notes.cannotRead") + e; }
  renderStages(); tick(); pollState(); showTab(LS.get("tab", "notes"));
})();
