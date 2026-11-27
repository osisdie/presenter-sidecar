"use strict";
// Step rule for the presenter panel, kept free of the DOM so tests/js can run it under node.
// Same rule as presenter_sidecar.notes.section_steps (tests/fixtures/steps checks both):
//  - a step is a paragraph whose ONLY content is a bold numbered title, "**3. Open the sheet**";
//    "3." needs a space before the title ("**2.5 million**" is not a step), "3．" may be followed directly;
//  - a section without any uses its ### headings instead;
//  - a step runs from its title to the next step, rule or heading (bold steps: also a quote / any heading;
//    ### steps: h1-h3 only).
const STEP_NUMBER = /^\d+(?:\.\s+|．\s*)\S/;

// block: { tag: "P" | "H3" | ..., text: visible text, trimmed, onlyStrong: the paragraph is one <strong> }
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
if (typeof module !== "undefined") module.exports = { STEP_NUMBER, boldStepTitle, planSteps };
