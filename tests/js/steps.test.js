"use strict";
// Runs the panel's step rule (web/md.js + web/steps.js) on tests/fixtures/steps, the same cases
// tests/test_steps.py runs through presenter_sidecar.notes.section_steps.  Run: node --test tests/js/*.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { md } = require("../../web/md.js");
const { planSteps, blockOf, stepMove, SPY_OFFSET, STEP_NUMBER } = require("../../web/steps.js");

const FIX = path.join(__dirname, "..", "fixtures", "steps");
const expected = JSON.parse(fs.readFileSync(path.join(FIX, "expected.json"), "utf8"));

// md() output → a minimal element tree (tagName, children, firstElementChild, textContent), so the
// panel's own blockOf() reads it exactly as it reads the DOM.
const unescape = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
const VOID = new Set(["BR", "HR"]);
function elem(tagName) {
  return { tagName, parts: [], children: [],
    get firstElementChild() { return this.children[0] || null; },
    get textContent() { return this.parts.map((x) => (typeof x === "string" ? x : x.textContent)).join(""); } };
}
function tree(html) {
  const root = elem("ARTICLE"), stack = [root], re = /<(\/?)([a-z0-9]+)[^>]*>|([^<]+)/gi;
  let m;
  while ((m = re.exec(html))) {
    const top = stack[stack.length - 1];
    if (m[3] != null) { top.parts.push(unescape(m[3])); continue; }
    const name = m[2].toUpperCase();
    if (m[1]) { stack.pop(); continue; }
    const el = elem(name); top.parts.push(el); top.children.push(el);
    if (!VOID.has(name)) stack.push(el);
  }
  return root;
}
const blocks = (html) => tree(html).children.map(blockOf);
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

test("blockOf: a <br> or text next to the <strong> is not a bold title", () => {
  assert.deepEqual(blocks(md("**1. a**\nmore")).map((b) => b.onlyStrong), [false]);
  assert.deepEqual(blocks(md("**1. a** tail")).map((b) => b.onlyStrong), [false]);
  assert.deepEqual(blocks(md("  **1. a `b`**  ")).map((b) => [b.onlyStrong, b.text]), [[true, "1. a b"]]);
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

// stepMove: view 0..500 (page = 400), steps described by the current one's box.
const view = { viewTop: 0, viewBottom: 500, atEnd: false };
const g = (o) => ({ n: 5, idx: 1, top: 4, bottom: 60, ...view, ...o });

test("stepMove: ↓ / ↑ between ordinary steps", () => {
  assert.deepEqual(stepMove(1, g()), { go: 2 });
  assert.deepEqual(stepMove(-1, g()), { go: 0 });
  assert.deepEqual(stepMove(-1, g({ idx: 0 })), { home: true });
  assert.deepEqual(stepMove(1, g({ n: 0 })), { by: 120 });
  assert.deepEqual(stepMove(-1, g({ n: 0 })), { by: -120 });
});

test("stepMove: ↓ first brings up a current step that is still below the view (entering a section)", () => {
  // step 1 selected on entry but 30 paragraphs down: the first ↓ shows step 1, not step 2
  assert.deepEqual(stepMove(1, g({ idx: 0, top: 1400, bottom: 1440 })), { go: 0 });
  assert.deepEqual(stepMove(1, g({ idx: 0, top: 480, bottom: 520 })), { go: 0 });      // title cut off at the bottom
  assert.deepEqual(stepMove(1, g({ idx: 0, top: 52, bottom: 90 })), { go: 1 });        // under the ## heading: seen
  assert.deepEqual(stepMove(1, g({ idx: 0, top: 387, bottom: 722 })), { go: 0 });      // title shown, body cut off
  assert.deepEqual(stepMove(1, g({ idx: 0, top: 4, bottom: 498 })), { go: 1 });        // brought up, fits
  assert.deepEqual(stepMove(1, g({ idx: 0, top: SPY_OFFSET, bottom: 40 })), { go: 1 }); // already up
  // at the bottom it can never come further up: move on instead of repeating forever
  assert.deepEqual(stepMove(1, g({ idx: 3, top: 480, bottom: 520, atEnd: true })), { go: 4 });
});

test("stepMove: ↓ on the last step reads on instead of jumping back to its title", () => {
  assert.deepEqual(stepMove(1, g({ idx: 4 })), { by: 400 });                         // short last step + tail
  assert.deepEqual(stepMove(1, g({ idx: 4, top: -900, bottom: 30, atEnd: true })), { by: 400 }); // wheel to bottom
  // tall last step: page to its end, then keep scrolling (never back to the title)
  assert.deepEqual(stepMove(1, g({ idx: 4, top: 4, bottom: 2000 })), { by: 400 });
  assert.deepEqual(stepMove(1, g({ idx: 4, top: -1500, bottom: 560 })), { by: 60 });
  assert.deepEqual(stepMove(1, g({ idx: 4, top: -1560, bottom: 500, atEnd: true })), { by: 400 });
});

test("stepMove: ↑ shows the current title again before moving back", () => {
  // reading the tail after the last step: ↑ goes back to that step's title, not the one before
  assert.deepEqual(stepMove(-1, g({ idx: 4, top: -900, bottom: -860, atEnd: true })), { go: 4 });
  assert.deepEqual(stepMove(-1, g({ idx: 4, top: 4, bottom: 44 })), { go: 3 });         // title in view
  assert.deepEqual(stepMove(-1, g({ idx: 0, top: -30, bottom: 30 })), { go: 0 });       // step 1 first ...
  assert.deepEqual(stepMove(-1, g({ idx: 0, top: 4, bottom: 60 })), { home: true });    // ... then the section top
});

test("stepMove: a tall step is paged through in both directions", () => {
  assert.deepEqual(stepMove(1, g({ top: 4, bottom: 1200 })), { by: 400 });
  assert.deepEqual(stepMove(1, g({ top: -800, bottom: 400 })), { go: 2 });      // its end is in view
  assert.deepEqual(stepMove(-1, g({ top: -800, bottom: 400 })), { by: -400 });
  assert.deepEqual(stepMove(-1, g({ top: -200, bottom: 1000 })), { go: 1 });    // title within a page: align it
});
