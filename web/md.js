"use strict";
// Mini Markdown renderer for the presenter panel (no DOM: also loaded by tests/js under node).
// presenter_sidecar.notes._blocks mirrors its block structure for the step rule.
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
if (typeof module !== "undefined") module.exports = { esc, inline, md };
