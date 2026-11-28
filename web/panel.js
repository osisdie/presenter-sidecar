"use strict";
// Presenter panel: speaker notes + section timers + optional AI helper.
// Talks only to panel_server.py on 127.0.0.1.
const $ = (s) => document.querySelector(s);
const store = (area) => ({
  get(k, d) { try { const v = area().getItem("presenter." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { area().setItem("presenter." + k, JSON.stringify(v)); } catch {} },
});
const LS = store(() => localStorage);
const SS = store(() => sessionStorage);  // per panel window (survives F5, not shared with other panels)
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
    "keys.restart": "Registered by mirror.py at its start: after changing hotkeys in config.json, restart the mirror.",
    "keys.fromConfig": "Mirror not connected: showing config.json. Changing hotkeys needs a mirror restart.",
    "keys.open": "Keyboard shortcuts", "keys.closeShort": "Close",
    "hk.pick": "Project the current foreground window", "hk.bring": "Move the source window next to the panel",
    "hk.freeze": "Freeze / unfreeze the projector (before typing anything private)",
    "hk.blank": "Blank “Please wait” screen / back", "hk.style": "Pointer style: ring ↔ spotlight",
    "hk.next": "Next notes section, from any window", "hk.prev": "Previous notes section, from any window",
    "hk.popups": "Follow popups: on / off", "hk.clip": "Confine the mouse to the presenter display: on / off",
    "hk.quit": "Quit the mirror (the panel stays open)",
    "pk.section": "Previous / next section", "pk.step": "Previous / next step (no steps: scroll)",
    "pk.home": "First section", "pk.keys": "Show / hide this list", "pk.reload": "Reload the panel (after editing notes or config)",
    "fold.preview": "Projector view", "fold.source": "Source", "fold.timer": "Timer", "fold.nav": "Notes & sections",
    "fold.chat": "Conversation", "preview.alt": "What the audience sees on the projector now",
    "preview.ageS": "{n} s ago", "preview.ageM": "{n} min ago", "preview.offline": "Mirror not connected",
    "preview.off": "Preview off", "preview.none": "No image yet",
    "preview.old": "Not updated for over {n} s", "preview.frozen": "Frozen", "preview.blank": "Blank",
    "profile.tip": "Profile: notes, timer sections and auto-follow rules switch together",
    "profile.label": "Profile", "profile.now": "Profile: {p}",
    "profile.followed": "Profile switched to {p}: the projected page matches its rules ({by}: {title})",
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
    "keys.restart": "以下是 mirror 啟動時註冊的熱鍵；改熱鍵需重開 mirror。",
    "keys.fromConfig": "mirror 未連線：顯示 config.json 的設定。改熱鍵需重開 mirror。",
    "keys.open": "快捷鍵一覽", "keys.closeShort": "關閉",
    "hk.pick": "把目前前景視窗設為投影來源", "hk.bring": "把來源視窗搬回筆電螢幕、放在面板旁邊",
    "hk.freeze": "凍結／解凍投影（輸入私人資料前先按）",
    "hk.blank": "「請稍候」畫面／切回", "hk.style": "游標樣式：光圈 ↔ 聚光燈",
    "hk.next": "講稿下一節（不用切到面板）", "hk.prev": "講稿上一節（不用切到面板）",
    "hk.popups": "自動跟隨彈窗：開／關", "hk.clip": "滑鼠鎖在講者螢幕：開／關",
    "hk.quit": "結束投影（面板留著）",
    "pk.section": "上一節／下一節", "pk.step": "這一節的上一步／下一步（沒有步驟時：捲動）",
    "pk.home": "回到第一節", "pk.keys": "開／關這張快捷鍵表", "pk.reload": "重新載入面板（改了講稿或設定後）",
    "fold.preview": "投影畫面", "fold.source": "投影來源", "fold.timer": "計時", "fold.nav": "講稿與章節",
    "fold.chat": "對話", "preview.alt": "觀眾現在在投影上看到的畫面",
    "preview.ageS": "{n} 秒前", "preview.ageM": "{n} 分鐘前", "preview.offline": "mirror 未連線",
    "preview.off": "預覽已關閉", "preview.none": "還沒有畫面",
    "preview.old": "超過 {n} 秒沒有更新", "preview.frozen": "凍結", "preview.blank": "請稍候",
    "profile.tip": "情境：講稿、計時段落和自動跟隨規則一起切換",
    "profile.label": "情境", "profile.now": "情境：{p}",
    "profile.followed": "已切到情境「{p}」：投影的頁面符合它的規則（依{by}：{title}）",
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
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => el.setAttribute("aria-label", T(el.dataset.i18nAria)));
  document.querySelectorAll("[data-i18n-alt]").forEach((el) => (el.alt = T(el.dataset.i18nAlt)));
  $("#aiIntro").innerHTML = CONF.ai_helper ? T("ai.intro") : T("ai.disabled");
  $("#askForm").hidden = !CONF.ai_helper;
  $("#tabAi").classList.toggle("off", !CONF.ai_helper);
  $("#mirror").textContent = T("mirror.offline");
}
const key = (action) => (mirrorHotkeys || CONF.hotkeys || {})[action] || "?";  // registered keys win (see renderKeys)

// esc / inline / md come from md.js; blockOf / planSteps / stepMove / SPY_OFFSET from steps.js;
// foldOpen / previewStatus / ageParts / PREVIEW_* from view.js (all loaded first).

// ------------------------------------------------------------ collapsible blocks
// <section class="fold" data-fold="name">: the header button toggles the body (aria-expanded, ▾ / ▸).
// Open / closed is saved per block ("fold.<name>"); defaults are FOLD_DEFAULTS in view.js. Collapsing
// only hides the body: the drop-downs and timers inside keep their state, so the hotkeys and the step
// scroll-spy work as before, and the notes article (flex: 1) takes the freed height.
const folds = {};
const foldIsOpen = (name) => folds[name]?.querySelector(".foldhead").getAttribute("aria-expanded") === "true";
function setFold(name, open, save = true) {
  const sec = folds[name]; if (!sec) return;
  const head = sec.querySelector(".foldhead");
  head.setAttribute("aria-expanded", String(open));
  head.querySelector(".chev").textContent = open ? "▾" : "▸";
  sec.querySelector(".foldbody").hidden = !open;
  sec.classList.toggle("closed", !open);
  if (!save) return;
  LS.set("fold." + name, open);
  if (name === "preview" && open) previewTick();  // show a fresh image right away
}
document.querySelectorAll(".fold").forEach((sec) => {
  const name = sec.dataset.fold; folds[name] = sec;
  setFold(name, foldOpen(name, LS.get("fold." + name, null)), false);
  sec.querySelector(".foldhead").onclick = () => setFold(name, !foldIsOpen(name));
});

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
// Each profile has its own sections and timer ("timer@<profile>"): switching never resets another one.
let stages = [];
const freshTimer = () => ({ cur: -1, starts: {}, classStart: null });
let timer = freshTimer();
const saveTimer = () => LS.set(profileKey("timer", profile), timer);
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
  const el = $("#stageTime"), bar = $("#stageBar"), sum = $("#timerSum");  // sum: shown while the block is closed
  if (s) {
    const ms = Date.now() - (timer.starts[s.key] || Date.now()), plan = s.minutes * 60000, r = ms / plan;
    el.textContent = `${mmss(ms)} / ${mmss(plan)}`;
    const cls = r >= 1 ? "over" : r >= 0.8 ? "warn" : "";
    el.className = "mono " + cls; bar.className = cls; bar.style.width = Math.min(100, r * 100) + "%";
    sum.textContent = `${s.short}  ${el.textContent}`;
    sum.className = "foldsum mono" + (cls === "over" ? " over" : cls === "warn" ? " warnt" : "");
  } else {
    el.textContent = "00:00 / 00:00"; el.className = "mono"; bar.style.width = "0";
    sum.textContent = T("timer.notStarted"); sum.className = "foldsum";
  }
  $("#classTime").textContent = timer.classStart ? mmss(Date.now() - timer.classStart) : "00:00";
}
$("#btnStart").onclick = () => startStage(0);
$("#btnNext").onclick = () => startStage(timer.cur + 1);
$("#btnResetTimer").onclick = () => {
  if (confirm(T("timer.confirmReset"))) { timer = freshTimer(); saveTimer(); renderStages(); tick(); }
};
setInterval(tick, 500);

// ------------------------------------------------------------ notes
let docs = [], docIdx = 0, sections = [], secIdx = 0, viewStage = -1;
// Open doc and section per doc are saved by notes path (as listed in notes_files), so adding or
// reordering notes files keeps your place; 0.1.0 saved them by position ("doc", "sec.<n>").
const secKey = () => `secs.${docs[docIdx]?.path}`;
function savedDoc() {
  const old = profileFallback("docPath", profile, profileNames);
  const i = docs.findIndex((d) => d.path === LS.get(profileKey("docPath", profile), old && LS.get(old, null)));
  return i >= 0 ? i : Math.min(LS.get("doc", 0), docs.length - 1);
}
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
// The timer section of notes section k (stageIndex in view.js; repeated headings count by occurrence).
function stageOfSection(k) {
  const t = sections[k].title.trim();
  return stageIndex(stages, t, sections.slice(0, k + 1).filter((s) => s.title.trim() === t).length);
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
  docIdx = Math.max(0, Math.min(docs.length - 1, i)); LS.set(profileKey("docPath", profile), docs[docIdx].path);
  sections = splitSections(docs[docIdx].text);
  const sel = $("#secSel"); sel.innerHTML = "";
  sections.forEach((s, k) => { const o = document.createElement("option"); o.value = k; o.textContent = `${k + 1}/${sections.length}　${s.title}`; sel.appendChild(o); });
  // sec == null: first load or reload, so return to the last section AND step; otherwise start at step 1.
  renderDocBar(); goSection(sec == null ? LS.get(secKey(), LS.get("sec." + docIdx, 0)) : sec, sec == null);
}
function goSection(k, restoreStep = false) {
  if (!sections.length) return;
  secIdx = Math.max(0, Math.min(sections.length - 1, k)); LS.set(secKey(), secIdx);
  $("#secSel").value = secIdx;
  const art = $("#note"); art.innerHTML = md(sections[secIdx].text); art.scrollTop = 0;
  buildSteps();
  if (steps.length) {
    const saved = restoreStep ? LS.get(stepKey(), 0) : 0;
    if (saved > 0) goStep(saved); else goStep(0, false);  // new section: step 1, scrolled to the top
  }
  viewStage = stageOfSection(secIdx);
  post("/api/panel", { profile, doc: docs[docIdx].name, section: sections[secIdx].title, index: `${secIdx + 1}/${sections.length}`, follow: notesFollow }).catch(() => {});
  const hint = $("#stageHint");
  if (viewStage >= 0 && viewStage !== timer.cur) {
    const v = esc(stages[viewStage].short), c = esc(stages[timer.cur]?.short || T("timer.notStarted"));
    hint.hidden = false;
    hint.innerHTML = `${T("stage.hint", { v, c })} <button id="syncStage">${T("stage.switch", { v })}</button>`;
    $("#syncStage").onclick = () => { startStage(viewStage); hint.hidden = true; };
  } else hint.hidden = true;
  renderStages(); navSummary();
}
function navSummary() {  // the "Notes & sections" block's one-line summary while it is closed
  const sec = sections[secIdx];
  $("#navSum").textContent = !sec ? "" : `${secIdx + 1}/${sections.length}　${sec.title}` +
    (steps.length ? " · " + T("step.label", { t: steps[stepIdx].title, i: stepIdx + 1, n: steps.length }) : "");
}
$("#secSel").onchange = (e) => { goSection(+e.target.value); e.target.blur(); };  // blur: arrow keys page again
$("#prev").onclick = () => goSection(secIdx - 1);
$("#next").onclick = () => goSection(secIdx + 1);

// ------------------------------------------------------------ steps inside a section
// The rule itself lives in steps.js (planSteps, shared with the Python mirror through
// tests/fixtures/steps). Each step (title + following blocks) is wrapped in <div class="step">
// so it can be highlighted and scrolled to.
let steps = [], stepIdx = 0, spyRaf = 0, spyMute = { until: 0, top: -1 };
// Saved step per section: notes path (as listed in notes_files) + section index, like secKey().
const stepKey = () => `steps.${docs[docIdx]?.path}#${secIdx}`;
function buildSteps() {
  const kids = [...$("#note").children];
  steps = planSteps(kids.map(blockOf)).map((p) => {
    const box = document.createElement("div"); box.className = "step";
    kids[p.start].before(box);
    for (let i = p.start; i < p.end; i++) box.appendChild(kids[i]);
    return { el: box, title: p.title };
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
  LS.set(stepKey(), stepIdx); navSummary();
  if (scroll) {
    const art = $("#note");
    art.scrollTop += steps[stepIdx].el.getBoundingClientRect().top - art.getBoundingClientRect().top - stickyOffset(art) - 4;
    // The scroll event this causes must not let the spy re-pick a step (a short step's successor sits
    // above the spy line). Muted only while the view is still where we put it: a hand scroll still counts.
    spyMute = { until: performance.now() + 400, top: art.scrollTop };
  }
}
function spyStep() {  // manual scrolling: the drop-down follows the step nearest the top
  spyRaf = 0;
  const art = $("#note");
  if (!steps.length || (performance.now() < spyMute.until && Math.abs(art.scrollTop - spyMute.top) < 2)) return;
  const top = art.getBoundingClientRect().top, line = top + stickyOffset(art) + SPY_OFFSET;
  let k = 0;
  for (let i = 0; i < steps.length; i++) { if (steps[i].el.getBoundingClientRect().top <= line) k = i; else break; }
  // At the bottom the last steps cannot reach the top: keep a later selected step while it is in view
  // (4 px slack: zoomed pages scroll in fractions and may stop just short of scrollHeight).
  const atEnd = art.scrollTop + art.clientHeight >= art.scrollHeight - 4;
  const cur = steps[stepIdx].el.getBoundingClientRect();
  if (atEnd && k < stepIdx && cur.top < top + art.clientHeight && cur.bottom > top) return;
  if (k !== stepIdx) goStep(k, false);
}
$("#note").addEventListener("scroll", () => { if (!spyRaf) spyRaf = requestAnimationFrame(spyStep); }, { passive: true });
$("#stepSel").onchange = (e) => { goStep(+e.target.value); e.target.blur(); };  // blur: ↑/↓ and J/K work right away
$("#stepPrev").onclick = () => goStep(stepIdx - 1);
$("#stepNext").onclick = () => goStep(stepIdx + 1);
function stepBy(d) {  // ↓ / ↑, J / K: the decision is stepMove() in steps.js
  const art = $("#note"), box = art.getBoundingClientRect(), cur = steps[stepIdx]?.el.getBoundingClientRect();
  const mv = stepMove(d, {
    n: steps.length, idx: stepIdx, top: cur?.top ?? 0, bottom: cur?.bottom ?? 0,
    viewTop: box.top + stickyOffset(art), viewBottom: box.bottom,
    atEnd: art.scrollTop + art.clientHeight >= art.scrollHeight - 4,
  });
  if (mv.by) art.scrollBy(0, mv.by);
  else if (mv.home) art.scrollTop = 0;
  else if (mv.go != null) goStep(mv.go);
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
// Global hotkeys: what mirror.py actually registered at its start (status `hotkeys`, keys another
// program holds flagged from `hotkeys_failed`). mirror.py reads `hotkeys` only when it starts, so
// config.json (/api/config) is shown only while the mirror is not connected.
let hotkeysFailed = [], mirrorHotkeys = null;
const kbds = (spec) => String(spec).split("+").map((k) => `<kbd>${esc(k.trim())}</kbd>`).join("+");
const keyRow = (keysHtml, desc, cls = "") => `<tr${cls ? ` class="${cls}"` : ""}><td>${keysHtml}</td><td>${desc}</td></tr>`;
function renderKeys() {
  const hk = mirrorHotkeys || CONF.hotkeys || {};
  $("#keysNote").textContent = T(mirrorHotkeys ? "keys.restart" : "keys.fromConfig");
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
// Modal: the page behind is `inert` while it is open, Tab / Shift+Tab cycle inside it, and closing
// returns focus to whatever had it before (the ⌨ button, a notes link, or nothing when opened with ?).
let keysReturn = null;
const keysFocusables = () => [...$("#keysOverlay").querySelectorAll("button, a[href], [tabindex]:not([tabindex='-1'])")];
function toggleKeys(show) {
  const o = $("#keysOverlay"), open = show === undefined ? o.hidden : show;
  if (open === !o.hidden) return;
  if (open) keysReturn = document.activeElement;
  o.hidden = !open;
  document.querySelectorAll("body > header, body > main, body > footer").forEach((el) => (el.inert = open));
  if (open) { $("#keysClose").focus(); return; }
  const back = keysReturn; keysReturn = null;
  if (back && back !== document.body && back.isConnected) back.focus();
  else document.activeElement?.blur();
}
$("#keysBtn").onclick = () => toggleKeys();
$("#keysClose").onclick = () => toggleKeys(false);
document.addEventListener("keydown", (e) => {
  const open = !$("#keysOverlay").hidden;
  if (open && e.key === "Tab") {  // focus trap
    const f = keysFocusables(), i = f.indexOf(document.activeElement);
    if (f.length) { f[(i + (e.shiftKey ? -1 : 1) + f.length) % f.length].focus(); e.preventDefault(); }
    return;
  }
  if (typing()) return;
  // "?" alone (Shift is part of typing it), or via AltGr, which browsers on Windows report as Ctrl+Alt.
  if (e.key === "?" && !e.metaKey && e.ctrlKey === e.altKey) {
    e.preventDefault(); e.stopImmediatePropagation();
    if (!e.repeat) toggleKeys();
  } else if (e.key === "Escape" && open && !(e.ctrlKey || e.altKey || e.metaKey)) {
    toggleKeys(false); e.preventDefault(); e.stopImmediatePropagation();
  }
}, true);

// ------------------------------------------------------------ notes auto-follow
// Jumps only when the projected page maps to a DIFFERENT section; manual paging is never overridden.
let notesFollow = null, lastNotesKey, webVersion = null, toastTimer = null;
function toast(msg, ms = 4000) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  t.style.bottom = $("#dock").offsetHeight + 8 + "px";  // above the projector preview dock
  clearTimeout(toastTimer); if (ms) toastTimer = setTimeout(() => (t.hidden = true), ms);
}
function renderFollowBtn() {
  const b = $("#followBtn"); b.textContent = T(notesFollow ? "follow.on" : "follow.off"); b.classList.toggle("on", !!notesFollow);
}
$("#followBtn").onclick = () => { notesFollow = !notesFollow; LS.set("notesFollow", notesFollow); renderFollowBtn(); };
function followTo(nt, msg) {
  let di = nt.doc ? docs.findIndex((d) => d.name === nt.doc || d.path.endsWith(nt.doc)) : docIdx;
  if (di < 0) di = docIdx;
  const secs = splitSections(docs[di].text);
  const k = secs.findIndex((x) => x.title.includes(nt.section));
  if (k < 0) return;
  if (di !== docIdx) openDoc(di, k); else goSection(k);
  toast(msg || T("notes.followed", { sec: secs[k].title, by: T("by." + nt.by), title: nt.title }));
}
async function handleNotesTarget(st) {
  if (notesFollow === null) { notesFollow = LS.get("notesFollow", st.notes_auto_follow_default !== false); renderFollowBtn(); }
  const nt = st.notes_target, k = targetKey(nt);
  if (!k) return;                                                     // no rule matched: stay
  if (lastNotesKey === undefined) { lastNotesKey = k; return; }       // panel just opened: keep your place
  if (k === lastNotesKey) return;                                     // same section: do not move
  lastNotesKey = k;
  if (!notesFollow) return;
  if (nt.profile && nt.profile !== profile) {                         // another profile's rule (profile_auto_switch)
    if (CONF.profile_auto_switch === false || !profileNames.includes(nt.profile)) return;
    await loadProfile(nt.profile);
    if (docs.length) followTo(nt, T("profile.followed", { p: nt.profile, by: T("by." + nt.by), title: nt.title }));
    return;
  }
  if (docs.length) followTo(nt);
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
  if (switching) return;  // a profile is loading: its notes and stages are not there yet
  try {
    const st = await (await fetch("/api/state?profile=" + encodeURIComponent(profile))).json();
    syncProfileNames(st.profiles);  // first: a request may name a profile added in this very poll
    if (switching) return;           // the active profile was removed: the first one is loading
    if (await handleProfileRequest(st.profile_req)) return;
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
    const hkNow = !stale && m.hotkeys && typeof m.hotkeys === "object" ? m.hotkeys : null;  // older mirrors: none
    if (failedNow.join() !== hotkeysFailed.join() || JSON.stringify(hkNow) !== JSON.stringify(mirrorHotkeys)) {
      hotkeysFailed = failedNow; mirrorHotkeys = hkNow; renderKeys();
    }
    const failed = failedNow.length ? T("hotkeys.failed", { k: failedNow.join(", ") }) : "";
    const w = stale ? "" : (m.warning || failed || m.notice || "");  // warnings win over notices
    warn.hidden = !w; warn.textContent = w;
    const info = !m.warning && !failed && m.notice;
    warn.className = "srcwarn small" + (info ? " info" : "");
    const sum = $("#sourceSum");  // closed block: a warning replaces the title, so it is never hidden
    sum.textContent = w ? (info ? w : "⚠ " + w) : $("#srcTitle").textContent;
    sum.className = "foldsum" + (w ? (info ? " info" : " warn") : "");
    renderPreview(st);
    await handleNotesTarget(st); handleVersion(st);
    const cmds = st.cmds || [];
    if (lastCmdSeq == null) lastCmdSeq = cmds.length ? cmds[cmds.length - 1].seq : 0;
    if (dropCmds) {  // Ctrl+Alt+PgUp / PgDn pressed while a profile was loading: not for the new notes
      dropCmds = false; if (cmds.length) lastCmdSeq = Math.max(lastCmdSeq, cmds[cmds.length - 1].seq);
    }
    for (const c of cmds) if (c.seq > lastCmdSeq) {
      lastCmdSeq = c.seq;
      if (c.nav) { showTab("notes"); goSection(secIdx + c.nav); }
    }
  } catch { $("#mirror").textContent = T("server.offline"); $("#mirror").className = "pill blank"; renderPreview(null); }
}
setInterval(pollState, 700);

// ------------------------------------------------------------ projector preview
// mirror.py writes logs/mirror.preview.jpg every ~2 s, only when the picture changed (frozen frame,
// blank screen and followed popups included). The panel fetches it only while the block is open and
// the page is visible, and greys it out when it is old or the mirror is not connected (last image).
let pvStatus = previewStatus(null), pvUrl = null, pvBusy = false;
const ageText = (secs) => { const a = ageParts(secs); return T(a.unit === "s" ? "preview.ageS" : "preview.ageM", { n: a.n }); };
function renderPreview(st) {
  const was = pvStatus.load, p = (pvStatus = previewStatus(st));
  const note = p.note === "old" ? T("preview.old", { n: PREVIEW_STALE_SECS }) : p.note ? T("preview." + p.note) : "";
  const badges = p.badges.map((b) => T("preview." + b));
  $("#preview").classList.toggle("stale", p.stale);
  $(".previewmeta").classList.toggle("stale", p.stale);
  $("#previewBadges").innerHTML = p.badges.map((b) => `<span class="pbadge ${b}">${esc(T("preview." + b))}</span>`).join("");
  $("#previewNote").textContent = note;
  $("#previewAge").textContent = p.age == null ? "" : ageText(p.age);
  $("#previewEmpty").textContent = note || T("preview.none");
  if (p.hide) { $("#previewImg").hidden = true; $("#previewEmpty").hidden = false; }  // never a stale screen in colour
  const sum = $("#previewSum");  // closed block: projector modes and problems only
  sum.textContent = [...badges, p.stale || p.note === "off" ? note : ""].filter(Boolean).join(" · ");
  sum.className = "foldsum" + (badges.length || p.stale ? " warn" : "");
  if (p.load && !was) previewTick();  // first image, or the mirror is back: do not wait for the interval
}
async function previewTick() {
  if (pvBusy || !pvStatus.load || !foldIsOpen("preview") || document.visibilityState !== "visible") return;
  pvBusy = true;
  try {
    // A hung request must not block every later refresh (pvBusy): give up after 5 s.
    const res = await fetch("/api/preview?t=" + Date.now(), { cache: "no-store", signal: AbortSignal.timeout(5000) });
    if (!res.ok) return;
    const url = URL.createObjectURL(await res.blob()), img = $("#previewImg");
    await new Promise((done) => {
      img.onload = () => {
        if (pvUrl) URL.revokeObjectURL(pvUrl);
        pvUrl = url;
        if (!pvStatus.hide) { img.hidden = false; $("#previewEmpty").hidden = true; }
        $("#preview").style.aspectRatio = `${img.naturalWidth} / ${img.naturalHeight}`;
        done();
      };
      img.onerror = () => { URL.revokeObjectURL(url); done(); };
      img.src = url;
    });
  } catch { /* server gone: the next poll greys the image out */ } finally { pvBusy = false; }
}
setInterval(previewTick, PREVIEW_REFRESH_MS);
document.addEventListener("visibilitychange", previewTick);

// ------------------------------------------------------------ profiles
// A profile = notes files + timer sections (pacing) + auto-follow rules; switching changes all three.
// The chip in the header is shown when the config has more than one.
let profile = "", profileNames = [], switching = null, dropCmds = false;
function renderProfileSel() {
  const sel = $("#profileSel");
  sel.innerHTML = profileNames.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
  sel.value = profile; sel.hidden = profileNames.length < 2;
}
async function loadProfile(name) {
  const run = (async () => {
    const q = "?profile=" + encodeURIComponent(name);
    const [pac, nts] = await Promise.all([fetch("/api/pacing" + q).then((r) => r.json()), fetch("/api/notes" + q).then((r) => r.json())]);
    // Only now: until both arrived, the old profile's timer and open file must keep saving under its own name.
    profile = name; LS.set("profile", name); renderProfileSel(); dropCmds = true;
    stages = pac.stages || [];
    const old = profileFallback("timer", name, profileNames);
    timer = LS.get(profileKey("timer", name), old ? LS.get(old, freshTimer()) : freshTimer());
    if (timer.cur >= stages.length) timer.cur = -1;
    docs = nts.docs || []; sections = []; steps = [];
    $("#docs").innerHTML = ""; $("#secSel").innerHTML = ""; $("#note").innerHTML = ""; $("#stepnav").hidden = true;
    if (docs.length) openDoc(savedDoc(), null); else { $("#stageHint").hidden = true; navSummary(); }
    renderStages(); tick();
  })();
  switching = run;
  try { await run; } finally { if (switching === run) switching = null; }
}
// Explicit startup request from the server (--profile, PRESENTER_PROFILE, start.ps1 -Profile): obeyed once
// per id by each panel window (the id seen is kept in sessionStorage, so F5 does not obey it again).
async function handleProfileRequest(req) {
  if (!req || !req.id || req.id === SS.get("profileReq", null)) return false;
  const pick = pickProfile(profileNames, profile, req, SS.get("profileReq", null));
  SS.set("profileReq", pick.seen);
  if (pick.name === profile) return false;
  await loadProfile(pick.name); toast(T("profile.now", { p: pick.name }));
  return true;
}
$("#profileSel").onchange = async (e) => { e.target.blur(); await loadProfile(e.target.value); };
// Profiles added, renamed or removed in config.json show up without F5; a removed active one falls back.
function syncProfileNames(names) {
  if (!Array.isArray(names) || !names.length || names.join("\u0001") === profileNames.join("\u0001")) return;
  profileNames = names;
  if (!names.includes(profile)) loadProfile(names[0]); else renderProfileSel();
}

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
  const timerId = setInterval(() => {
    prog.textContent = `⏳ ${T("ai.secs", { n: Math.round((Date.now() - t0) / 1000) })} · ${status}`;
    $("#chatSum").textContent = prog.textContent;  // shown while the conversation block is closed
  }, 250);
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
    clearInterval(timerId); prog.hidden = true; aborter = null; $("#chatSum").textContent = "";
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
  profileNames = Array.isArray(CONF.profiles) && CONF.profiles.length ? CONF.profiles : ["default"];
  const pick = pickProfile(profileNames, LS.get("profile", null), CONF.profile_req, SS.get("profileReq", null));
  SS.set("profileReq", pick.seen);
  try { await loadProfile(pick.name); } catch (e) { $("#note").textContent = T("notes.cannotRead") + e; }
  renderStages(); tick(); pollState(); showTab(LS.get("tab", "notes"));
})();
