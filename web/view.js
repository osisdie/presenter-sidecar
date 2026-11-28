"use strict";
// View rules for the panel that do not touch the DOM (tests/js/view.test.js runs them under node):
// which blocks start collapsed, and how the projector preview is shown.

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

// st: /api/state. Returns { connected, load, stale, note, age, badges }:
//  - load: there is an image worth fetching (mirror connected and a file exists);
//  - note: null, "offline" (mirror not connected: last image), "off" (preview_interval_sec is 0),
//    "none" (no image yet) or "old" (older than PREVIEW_STALE_SECS);
//  - stale: grey the image out (offline or old);
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
    stale: note === "offline" || note === "old" };
}

// Seconds → { n, unit } for "3 s ago" / "2 min ago".
function ageParts(secs) {
  const s = Math.max(0, Math.round(secs));
  return s < 60 ? { n: s, unit: "s" } : { n: Math.floor(s / 60), unit: "min" };
}

if (typeof module !== "undefined") {
  module.exports = { FOLD_DEFAULTS, foldOpen, PREVIEW_REFRESH_MS, PREVIEW_STALE_SECS, MIRROR_STALE_SECS,
    previewStatus, ageParts };
}
