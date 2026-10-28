// md.js — small Markdown renderer for the pipeline's notes (headings, lists, checkboxes, tables,
// quotes, bold/italic/code, [[wikilinks]]). Input is escaped first; nothing is passed through raw.
(function () {
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  function inline(s, people) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_, target, label) => {
      const name = target.trim(), shown = (label || target).trim();
      return people.has(name) ? `<a class="p" href="#" data-act="person" data-id="${name}">${shown}</a>` : shown;
    });
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, '$1<em>$2</em>');
    s = s.replace(/(^|\s)_([^_\n]+)_(?=\s|$|[.,;:])/g, '$1<em>$2</em>');
    return s;
  }

  function render(md, peopleNames) {
    const people = new Set(peopleNames || []);
    const lines = md.replace(/\r/g, '').split('\n');
    const out = [];
    const stack = [];                              // open lists: {type, indent}
    let para = [];
    const flushPara = () => { if (para.length) { out.push('<p>' + inline(para.join(' '), people) + '</p>'); para = []; } };
    const closeLists = (toIndent) => {
      while (stack.length && stack[stack.length - 1].indent >= toIndent) {
        out.push(`</li></${stack.pop().type}>`);
      }
    };
    for (let i = 0; i < lines.length; i++) {
      const ln = lines[i];
      if (/^```/.test(ln)) {                       // code fence (mermaid etc.): skip the block
        flushPara(); closeLists(0);
        while (++i < lines.length && !/^```/.test(lines[i])) {}
        continue;
      }
      if (!ln.trim()) { flushPara(); continue; }
      let m;
      if ((m = ln.match(/^(#{2,6})\s+(.*)$/))) {
        flushPara(); closeLists(0);
        const lvl = m[1].length <= 2 ? 'h4' : 'h5';
        out.push(`<${lvl}>${inline(m[2], people)}</${lvl}>`);
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(ln) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
        flushPara(); closeLists(0);
        const cells = r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => inline(c.trim(), people));
        let h = '<div class="tw"><table><thead><tr>' + cells(ln).map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>';
        i += 2;
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
          h += '<tr>' + cells(lines[i]).map(c => `<td>${c}</td>`).join('') + '</tr>'; i++;
        }
        i--;
        out.push(h + '</tbody></table></div>');
        continue;
      }
      if ((m = ln.match(/^>\s?(.*)$/))) {
        flushPara(); closeLists(0);
        out.push('<blockquote>' + inline(m[1], people) + '</blockquote>');
        continue;
      }
      if ((m = ln.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/))) {
        flushPara();
        const indent = m[1].replace(/\t/g, '    ').length;
        const type = /\d/.test(m[2]) ? 'ol' : 'ul';
        const top = stack[stack.length - 1];
        if (!top || indent > top.indent) {
          out.push(`<${type}>`); stack.push({ type, indent });
        } else {
          closeLists(indent + 1);
          const t2 = stack[stack.length - 1];
          if (!t2 || t2.indent < indent) { out.push(`<${type}>`); stack.push({ type, indent }); }
          else out.push('</li>');
        }
        let text = m[3], cls = '';
        const cb = text.match(/^\[([ xX])\]\s*(.*)$/);
        if (cb) {
          cls = cb[1] === ' ' ? 'cb' : 'cb x';
          out.push(`<li class="${cls}"><span class="box"></span><span class="tx">${inline(cb[2], people)}</span>`);
        } else {
          out.push('<li>' + inline(text, people));
        }
        continue;
      }
      if (stack.length && /^\s+\S/.test(ln)) {     // continuation of a list item
        out.push(' ' + inline(ln.trim(), people));
        continue;
      }
      closeLists(0);
      para.push(ln.trim());
    }
    flushPara(); closeLists(0);
    return out.join('\n');
  }
  window.MD = { render, inline, esc };
})();
