"use strict";
// Step rule for the presenter panel, kept free of the DOM so tests/js can run it under node.
// Same rule as presenter_sidecar.notes.section_steps (tests/fixtures/steps checks both):
//  - a step is a paragraph whose ONLY content is a bold numbered title, "**3. Open the sheet**";
//    ASCII digits only; "3." needs a space before the title ("**2.5 million**" is not a step), "3．" may
//    be followed directly;
//  - a section without any uses its ### headings instead;
//  - a step runs from its title to the next step, rule or heading (bold steps: also a quote / any heading;
//    ### steps: h1-h3 only).
const STEP_NUMBER = /^[0-9]+(?:\.\s+|．\s*)\S/;
// The scroll-spy line sits this far below the top of the notes view (under any sticky header).
const SPY_OFFSET = 8;
// A step whose top is less than this above the bottom of the view has no readable title on screen.
const TITLE_PX = 40;

// block: { tag: "P" | "H3" | ..., text: visible text, trimmed, onlyStrong: the paragraph is one <strong> }
// blockOf reads it from an element: anything with tagName, textContent, children and firstElementChild
// (a DOM element in the panel, a small stand-in in tests/js).
function blockOf(el) {
  const text = el.textContent.trim(), first = el.firstElementChild;
  return { tag: el.tagName, text,
    onlyStrong: el.children.length === 1 && first.tagName === "STRONG" && text === first.textContent.trim() };
}
function boldStepTitle(block) {
  return block.tag === "P" && block.onlyStrong && STEP_NUMBER.test(block.text) ? block.text : null;
}

// blocks: the section's top-level elements in order. Returns [{ start, end, title }] where blocks
// start..end-1 belong to the step (end is exclusive).
function planSteps(blocks) {
  let heads = [], bold = true;
  blocks.forEach((b, i) => { if (boldStepTitle(b) != null) heads.push(i); });
  if (!heads.length) { blocks.forEach((b, i) => { if (b.tag === "H3") heads.push(i); }); bold = false; }
  const isHead = new Set(heads);
  const ends = (b, i) => isHead.has(i) || b.tag === "HR" ||
    (bold ? /^H[1-6]$/.test(b.tag) || b.tag === "BLOCKQUOTE" : /^H[1-3]$/.test(b.tag));
  return heads.map((h) => {
    let e = h + 1;
    while (e < blocks.length && !ends(blocks[e], e)) e++;
    return { start: h, end: e, title: bold ? boldStepTitle(blocks[h]) : blocks[h].text };
  });
}
// What ↓ (d = 1) / ↑ (d = -1) does in the notes view. g: { n: step count, idx: current step,
// top / bottom: current step's box, viewTop: top of the view below sticky headers, viewBottom,
// atEnd: scrolled to the bottom } (all in the same coordinates). Returns one of
// { by: px } scroll the notes, { go: k } select step k and scroll it to the top, { home: true } scroll to 0.
function stepMove(d, g) {
  if (!g.n) return { by: d * 120 };                          // no steps in this section: scroll
  const view = g.viewBottom - g.viewTop, page = Math.round(view * 0.8), tall = g.bottom - g.top > view;
  if (d > 0) {
    // The current step's title is not on screen yet (entering a section selects step 1 without
    // scrolling, and it may be below the fold): bring it up before moving on. A visible step 1 just
    // under the section heading counts as seen, so the first ↓ there still goes to step 2.
    if (g.top > g.viewBottom - TITLE_PX && !g.atEnd) return { go: g.idx };
    // A step taller than the view: page through it, stopping at its end.
    if (tall && g.bottom > g.viewBottom + 2) return { by: Math.min(page, Math.ceil(g.bottom - g.viewBottom)) };
    if (g.idx >= g.n - 1) return { by: page };                // past the last step: read on to the section end
    return { go: g.idx + 1 };
  }
  if (tall && g.top < g.viewTop - 2) return g.viewTop + 4 - g.top > page ? { by: -page } : { go: g.idx };
  if (g.idx <= 0) return { home: true };                      // up from step 1: back to the section top
  return { go: g.idx - 1 };
}
if (typeof module !== "undefined") module.exports = { STEP_NUMBER, SPY_OFFSET, blockOf, boldStepTitle, planSteps, stepMove };
