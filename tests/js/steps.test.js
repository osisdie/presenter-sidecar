"use strict";
// Runs the panel's step rule (web/md.js + web/steps.js) on tests/fixtures/steps, the same cases
// tests/test_steps.py runs through presenter_sidecar.notes.section_steps.  Run: node --test tests/js/*.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { md } = require("../../web/md.js");
const { planSteps, STEP_NUMBER } = require("../../web/steps.js");

const FIX = path.join(__dirname, "..", "fixtures", "steps");
const expected = JSON.parse(fs.readFileSync(path.join(FIX, "expected.json"), "utf8"));

// md() output → top-level blocks, as panel.js blockOf() reads them from the DOM.
const unescape = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
function blocks(html) {
  const re = /<(\/?)([a-z0-9]+)[^>]*>/gi, out = [];
  let depth = 0, start = 0, tag = "", m;
  while ((m = re.exec(html))) {
    const name = m[2].toUpperCase();
    if (name === "BR" || name === "HR") { if (name === "HR" && depth === 0) out.push({ tag: "HR", inner: "" }); continue; }
    if (!m[1]) { if (depth++ === 0) { start = re.lastIndex; tag = name; } }
    else if (--depth === 0) out.push({ tag, inner: html.slice(start, m.index) });
  }
  return out.map(({ tag, inner }) => ({
    tag, text: unescape(inner.replace(/<[^>]+>/g, "")).trim(),
    onlyStrong: /^<strong>(?:(?!<\/?strong>)[\s\S])*<\/strong>$/.test(inner.trim()),
  }));
}
const titles = (src) => planSteps(blocks(md(src))).map((s) => s.title);

test("every fixture has expected titles", () => {
  const files = fs.readdirSync(FIX).filter((f) => f.endsWith(".md")).sort();
  assert.deepEqual(files, Object.keys(expected).sort());
});

for (const [name, want] of Object.entries(expected)) {
  test(`fixture ${name}`, () => {
    assert.deepEqual(titles(fs.readFileSync(path.join(FIX, name), "utf8")), want);
  });
}

test("step number needs a space after an ASCII dot", () => {
  assert.ok(STEP_NUMBER.test("2. Two"));
  assert.ok(STEP_NUMBER.test("10．全形"));
  assert.ok(!STEP_NUMBER.test("2.5 million"));
  assert.ok(!STEP_NUMBER.test("1.Title"));
  assert.ok(!STEP_NUMBER.test("1. "));
});

test("segments: a bold step stops at a quote, rule or heading", () => {
  const b = blocks(md("**1. A**\n\ntext\n\n> quote\n\n**2. B**\n\n- x\n\n---\n\nafter\n\n**3. C**\n\n#### h4\n"));
  const plan = planSteps(b).map(({ start, end }) => b.slice(start, end).map((x) => x.tag).join(" "));
  assert.deepEqual(plan, ["P P", "P UL", "P"]);
});

test("segments: an ### step runs past h4 but stops at the next h3 or rule", () => {
  const b = blocks(md("### One\n\ntext\n\n#### deeper\n\n> quote\n\n### Two\n\n---\n\ntail\n"));
  const plan = planSteps(b).map(({ start, end }) => b.slice(start, end).map((x) => x.tag).join(" "));
  assert.deepEqual(plan, ["H3 P H4 BLOCKQUOTE", "H3"]);
});
