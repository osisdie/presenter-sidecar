"use strict";
// View rules for the panel that do not touch the DOM (tests/js/view.test.js runs them under node):
// which blocks start collapsed, how the projector preview is shown (and what clicking it says), and which
// profile to open.

// Collapsible blocks (data-fold in index.html). Saved per block in localStorage ("fold.<name>");
// a block never toggled uses its default here. The preview starts collapsed (it is a check, not
// something to watch); everything else starts open, as before 0.3.0.
const FOLD_DEFAULTS = { preview: false, source: true, timer: true, nav: true, chat: true };
function foldOpen(name, saved) {
  if (typeof saved === "boolean") return saved;
  return FOLD_DEFAULTS[name] ?? true;
}

// Projector preview.
const PREVIEW_REFRESH_MS = 2000;   // reload the image this often, only while open and visible
const PREVIEW_STALE_SECS = 10;     // older than this: greyed out with a note
const MIRROR_STALE_SECS = 4;       // same as panel_server.MIRROR_STALE_SECS

// st: /api/state. Returns { connected, load, stale, hide, note, age, badges }:
//  - load: there is an image worth fetching (mirror connected and a file exists);
//  - note: null, "offline" (mirror not connected: last image), "off" (preview turned off: config or an
//    error), "none" (no image: not written yet, or deleted by a mirror restart) or "old" (older than
//    PREVIEW_STALE_SECS);
//  - stale: grey the last image out (offline or old);
//  - hide: do not show the last image at all ("off" / "none": it may be a previous run's screen);
//  - badges: projector modes the audience sees now ("blank" wins over "frozen" on the projector,
//    so it comes first).
function previewStatus(st, staleSecs = PREVIEW_STALE_SECS) {
  const s = st || {}, m = s.mirror || {}, p = s.preview || {};
  const connected = typeof s.mirror_age === "number" && s.mirror_age <= MIRROR_STALE_SECS;
  const age = typeof p.age === "number" ? p.age : null;
  const badges = connected ? [m.blank && "blank", m.frozen && "frozen"].filter(Boolean) : [];
  let note = null;
  if (!connected) note = "offline";
  else if (p.enabled === false) note = "off";
  else if (!p.available) note = "none";
  else if (age == null || age > staleSecs) note = "old";
  return { connected, load: connected && !!p.available && p.enabled !== false, age, badges, note,
    stale: note === "offline" || note === "old", hide: note === "off" || note === "none" };
}

// Seconds → { n, unit } for "3 s ago" / "2 min ago".
function ageParts(secs) {
  const s = Math.max(0, Math.round(secs));
  return s < 60 ? { n: s, unit: "s" } : { n: Math.floor(s / 60), unit: "min" };
}

// Clicking the projector preview (POST /api/focus). r: the server's reply, or null when the request failed.
// Returns the i18n key of the toast: "focus.popup" / "focus.source" (the mirror will bring that window to the
// front), "focus.noSource" (nothing projected yet: press the pick hotkey), "focus.offline" (mirror not
// connected: nothing was queued) or "focus.failed".
function focusToast(r) {
  if (!r || !r.ok) return "focus.failed";
  if (!r.mirror) return "focus.offline";
  if (r.target === "popup" || r.target === "source") return "focus." + r.target;
  return "focus.noSource";
}
// A key that presses a role="button" element: Enter or Space, without modifiers or auto-repeat.
function activatesButton(e) {
  return (e.key === "Enter" || e.key === " ") && !e.repeat && !e.ctrlKey && !e.altKey && !e.metaKey && !e.isComposing;
}

// Profiles. names: from /api/config; saved: the profile last shown in this panel; req: the server's
// startup profile { name, id }. id is set only for an explicit request (--profile / PRESENTER_PROFILE /
// "profile" in the config / start.ps1 -Profile); seen: the last request id this panel obeyed. An explicit request wins once per
// panel; after that, F5 (and a plain server restart: no id) keeps the profile you picked by hand.
// Returns { name, seen, requested }.
function pickProfile(names, saved, req, seen) {
  const ok = (n) => typeof n === "string" && names.includes(n);
  if (req && req.id && req.id !== seen && ok(req.name)) return { name: req.name, seen: req.id, requested: true };
  const next = req && req.id ? req.id : seen;
  if (ok(saved)) return { name: saved, seen: next, requested: false };
  return { name: req && ok(req.name) ? req.name : names[0] ?? "", seen: next, requested: false };
}
// localStorage key of a per-profile value ("timer", "docPath"). profileFallback: the 0.2.0 key, read only
// for the first profile, so a config without profiles keeps its running timer and open file.
function profileKey(base, profile) { return `${base}@${profile}`; }
function profileFallback(base, profile, names) { return profile === names[0] ? base : null; }
// The timer section of a notes section: the stage made from exactly this section (pacing_notes: same
// heading and occurrence nth, so repeated headings keep their own timer), else the longest stage short
// name found in the heading (pacing_file). Same rule as presenter_sidecar.notes.stage_for_section.
function stageIndex(stages, title, nth = 1) {
  const t = String(title).trim();
  const exact = stages.findIndex((s) => s.heading === t && (s.nth ?? 1) === nth);
  if (exact >= 0) return exact;
  const h = t.toLowerCase(); let best = -1, len = 0;
  stages.forEach((s, i) => { const n = s.short.toLowerCase(); if (n && h.includes(n) && n.length > len) { best = i; len = n.length; } });
  return best;
}
// Auto-follow target identity: the same section name in another profile is another target.
function targetKey(nt) { return nt && nt.key ? `${nt.profile ?? ""}\u0001${nt.key}` : null; }

if (typeof module !== "undefined") {
  module.exports = { FOLD_DEFAULTS, foldOpen, PREVIEW_REFRESH_MS, PREVIEW_STALE_SECS, MIRROR_STALE_SECS,
    previewStatus, ageParts, focusToast, activatesButton, pickProfile, profileKey, profileFallback, targetKey, stageIndex };
}
