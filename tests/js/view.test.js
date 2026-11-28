"use strict";
// Panel view rules without the DOM (web/view.js): collapsible block defaults and the projector preview status.
// Run: node --test tests/js/*.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { FOLD_DEFAULTS, foldOpen, PREVIEW_STALE_SECS, previewStatus, ageParts, pickProfile, profileKey, profileFallback,
  targetKey } = require("../../web/view.js");

test("fold defaults: preview closed, notes and everything else open", () => {
  assert.equal(foldOpen("preview", null), false);
  assert.equal(foldOpen("nav", null), true);
  for (const name of ["source", "timer", "chat"]) assert.equal(foldOpen(name, undefined), true);
  assert.equal(foldOpen("someFutureBlock", null), true);
  assert.deepEqual(Object.keys(FOLD_DEFAULTS).sort(), ["chat", "nav", "preview", "source", "timer"]);
});

test("a saved fold state wins over the default; anything but a boolean is ignored", () => {
  assert.equal(foldOpen("preview", true), true);
  assert.equal(foldOpen("nav", false), false);
  assert.equal(foldOpen("preview", "true"), false);
  assert.equal(foldOpen("nav", 0), true);
});

const st = (mirrorAge, preview, mirror = {}) => ({ mirror_age: mirrorAge, mirror, preview });

test("fresh image: load it, nothing to note", () => {
  const p = previewStatus(st(0.5, { available: true, enabled: true, age: 1.2 }));
  assert.deepEqual(p, { connected: true, load: true, age: 1.2, badges: [], note: null, stale: false, hide: false });
});

test("older than the stale limit: greyed out but still loaded", () => {
  const p = previewStatus(st(0.5, { available: true, enabled: true, age: PREVIEW_STALE_SECS + 0.1 }));
  assert.equal(p.note, "old"); assert.equal(p.stale, true); assert.equal(p.load, true);
  assert.equal(previewStatus(st(0.5, { available: true, enabled: true, age: PREVIEW_STALE_SECS })).stale, false);
  assert.equal(previewStatus(st(0.5, { available: true, enabled: true, age: null })).note, "old");
});

test("mirror not connected: keep the last image greyed, do not fetch", () => {
  for (const s of [st(4.1, { available: true, age: 30 }), st(null, { available: true }), null, {}]) {
    const p = previewStatus(s);
    assert.equal(p.connected, false); assert.equal(p.load, false);
    assert.equal(p.note, "offline"); assert.equal(p.stale, true); assert.deepEqual(p.badges, []);
  }
});

test("preview off or no image yet: nothing to fetch, not greyed", () => {
  const off = previewStatus(st(1, { available: false, enabled: false, age: null }));
  assert.equal(off.note, "off"); assert.equal(off.load, false); assert.equal(off.stale, false);
  const none = previewStatus(st(1, { available: false, enabled: true, age: null }));
  assert.equal(none.note, "none"); assert.equal(none.load, false); assert.equal(none.stale, false);
  // Neither may keep showing an earlier picture (an encode error, or a mirror restart deleted the file).
  assert.equal(off.hide, true); assert.equal(none.hide, true);
  assert.equal(previewStatus(st(9, { available: true })).hide, false);  // offline: last picture, greyed
  // A mirror before 0.3.0 reports no preview at all.
  assert.equal(previewStatus(st(1, undefined)).note, "none");
});

test("badges follow the projector mode: blank first (it covers a frozen frame)", () => {
  const pv = { available: true, enabled: true, age: 1 };
  assert.deepEqual(previewStatus(st(1, pv, { frozen: true })).badges, ["frozen"]);
  assert.deepEqual(previewStatus(st(1, pv, { blank: true })).badges, ["blank"]);
  assert.deepEqual(previewStatus(st(1, pv, { blank: true, frozen: true })).badges, ["blank", "frozen"]);
  assert.deepEqual(previewStatus(st(9, pv, { blank: true })).badges, []);  // stale status says nothing
});

test("age in seconds, then minutes", () => {
  assert.deepEqual(ageParts(0), { n: 0, unit: "s" });
  assert.deepEqual(ageParts(3.4), { n: 3, unit: "s" });
  assert.deepEqual(ageParts(59.4), { n: 59, unit: "s" });
  assert.deepEqual(ageParts(61), { n: 1, unit: "min" });
  assert.deepEqual(ageParts(-2), { n: 0, unit: "s" });
});

const NAMES = ["talk", "meeting"];

test("profile: a new startup request wins once", () => {
  assert.deepEqual(pickProfile(NAMES, "talk", { name: "meeting", id: "b-0" }, "a-0"),
    { name: "meeting", seen: "b-0", requested: true });
  // F5 afterwards: same request id, so the profile picked by hand stays.
  assert.deepEqual(pickProfile(NAMES, "talk", { name: "meeting", id: "b-0" }, "b-0"),
    { name: "talk", seen: "b-0", requested: false });
});

test("profile: first open, unknown names and no request", () => {
  assert.equal(pickProfile(NAMES, null, { name: "meeting", id: "x" }, null).name, "meeting");
  assert.equal(pickProfile(NAMES, "gone", { name: "meeting", id: "x" }, "x").name, "meeting");
  assert.equal(pickProfile(NAMES, null, { name: "gone", id: "y" }, null).name, "talk");
  assert.deepEqual(pickProfile(NAMES, "meeting", null, null), { name: "meeting", seen: null, requested: false });
  assert.equal(pickProfile([], null, null, null).name, "");
});

test("profile storage keys: per profile, 0.2.0 keys only for the first", () => {
  assert.equal(profileKey("timer", "meeting"), "timer@meeting");
  assert.equal(profileFallback("timer", "talk", NAMES), "timer");
  assert.equal(profileFallback("timer", "meeting", NAMES), null);
});

test("auto-follow target key includes the profile", () => {
  assert.equal(targetKey(null), null);
  assert.equal(targetKey({ key: null, profile: "talk" }), null);
  assert.notEqual(targetKey({ key: "Q&A", profile: "talk" }), targetKey({ key: "Q&A", profile: "meeting" }));
  assert.equal(targetKey({ key: "Q&A" }), targetKey({ key: "Q&A", profile: "" }));
});
