// app.js — Meeting Notes app. Vanilla JS, no build step; all data comes from the server's /api/*.
'use strict';
const esc = MD.esc;
const $ = s => document.querySelector(s);
const ICON = {
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
  week: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4.5" width="18" height="16.5" rx="2.5"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4M7.5 14h4M7.5 17.5h8"/></svg>',
  people: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5"/><circle cx="17" cy="9" r="2.6"/><path d="M17 14.6c2.5.2 4.1 1.9 4.5 4.9"/></svg>',
  ask: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.5 8.5 0 0 1-12.4 7.6L3 21l1.9-5.4A8.5 8.5 0 1 1 21 11.5z"/><path d="M9.6 9.3a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2-2.4 3.4M12 16.4h.01"/></svg>',
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  chev: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>',
  pen: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19.5 8.5a2.8 2.8 0 0 0-4-4L4 16z"/><path d="M13.5 6.5l4 4"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15l13-7.5z"/></svg>',
  pause: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4.5" width="4.5" height="15" rx="1"/><rect x="13.5" y="4.5" width="4.5" height="15" rx="1"/></svg>',
  lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="10.5" width="15" height="10.5" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>',
  camera: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/></svg>',
  speaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9.5h3.5L12 5v14l-4.5-4.5H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>'
};
const FORMAT = { group: 'Group meeting', 'one-on-one': 'One-on-one', interview: 'Interview', presentation: 'Presentation',
  customer: 'Customer', call: 'Call', huddle: 'Huddle', 'hr-conversation': 'HR conversation' };

let D = null;                    // /api/data
let S = { tab: 'home', view: null, id: null, q: '', results: null, ask: null, showAllTodos: false, showDone: false };
const stack = [];
const bodies = {};               // meeting id -> markdown
let offline = false;

// ------------------------------------------------------------ data
function saveCopy(d) { try { localStorage.setItem('data', JSON.stringify(d)); } catch (e) {} }
function loadCopy() { try { return JSON.parse(localStorage.getItem('data') || 'null'); } catch (e) { return null; } }

async function api(path, body) {
  const opt = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-App': '1' }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  let j = {};
  try { j = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error(j.error || 'Your Mac didn’t answer.');
  return j;
}

async function refresh(quiet) {
  try {
    const d = await api('/api/data');
    D = d; offline = false; saveCopy(d);
  } catch (e) {
    if (!D) D = loadCopy();
    offline = true;
    if (!D) { $('#main').innerHTML = '<p class="loading">Can’t reach your Mac. Away from home? Check that Tailscale is on, then pull to refresh.</p>'; return; }
  }
  const typing = document.activeElement && ['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName);
  if (!quiet || !(document.querySelector('.scrim') || typing)) { const y = window.scrollY; render(); if (quiet) window.scrollTo(0, y); }
}

const M = id => D.meetings.find(m => m.id === id);
const P = name => D.people.find(p => p.name === name);
const T = id => D.todos.find(t => t.id === id);

// ------------------------------------------------------------ formatting
function dateLabel(iso, long) {
  const d = new Date(iso + 'T12:00:00');
  if (isNaN(d)) return iso;
  const days = Math.round((new Date(D.today + 'T12:00:00') - d) / 864e5);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7 && !long) return d.toLocaleDateString(undefined, { weekday: 'long' });
  return d.toLocaleDateString(undefined, long ? { weekday: 'long', month: 'short', day: 'numeric' } : { month: 'short', day: 'numeric' });
}
const fmt = s => esc(s || '').replace(/\*\*(.+?)\*\*/g, '<mark>$1</mark>');
const initials = n => n.replace(/["“”].*?["“”]/g, '').split(/\s+/).filter(Boolean).map(w => w[0]).slice(0, 2).join('').toUpperCase();
const mins = m => m.minutes === null || m.minutes === undefined ? '' : (m.minutes < 1 ? 'under 1 min' : m.minutes + ' min');
const kind = m => m.format ? (FORMAT[m.format] || m.format) : ({ training: 'Training', learning: 'Learning', idea: 'Idea', meeting: 'Meeting', note: 'Note' }[m.type] || m.category);
const toSecs = ts => ts.split(':').map(Number).reduce((a, b) => a * 60 + b, 0);
function ago(t) {
  const s = Date.now() / 1000 - t;
  if (s < 3600) return Math.max(1, Math.round(s / 60)) + ' min ago';
  if (s < 86400) return Math.round(s / 3600) + ' hr ago';
  const d = Math.round(s / 86400);
  return d === 1 ? 'yesterday' : d + ' days ago';
}
function tsBtn(m, at) {
  return at && m.has_audio ? `<button class="ts" data-act="ts" data-id="${m.id}" data-t="${esc(at)}" aria-label="Play from ${esc(at)}">▶ ${esc(at)}</button>` : '';
}

// ------------------------------------------------------------ pieces
function todoRow(t, showSrc, withTs) {
  const m = M(t.meeting);
  return `<div class="row ${t.done ? 'done' : ''}"><button class="tick" data-act="todo" data-id="${t.id}" aria-pressed="${t.done}">
    <span class="check">${ICON.check}</span>
    <span class="body"><span class="t">${t.kind === 'delegate' ? '<span class="tag">HAND OFF</span>' : ''}${esc(t.text)}</span>
    ${showSrc && m ? `<br><span class="m">${esc(m.title)} · ${dateLabel(m.date)}</span>` : ''}</span></button>
    ${withTs && m ? `<span class="right">${tsBtn(m, t.at)}</span>` : ''}</div>`;
}
function waitRow(w, showSrc) {
  const m = M(w.meeting);
  return `<div class="row"><span class="avatar">${esc(initials(w.who))}</span>
    <button class="body" style="text-align:left" data-act="${w.known ? 'person' : 'meeting'}" data-id="${esc(w.known ? w.who : w.meeting)}">
      <span class="t">${esc(w.what)}</span><br><span class="m">${esc(w.who)}${showSrc && m ? ' · ' + esc(m.title) : ''}</span></button>
    <span class="right">${w.due ? esc(w.due) + '<br>' : ''}<button class="handled" data-act="handled" data-id="${w.key}">Got it</button></span></div>`;
}
function mRow(m) {
  const open = m.todos.filter(t => !t.done).length;
  const point = m.tldr ? m.tldr.point : m.summary;
  return `<button class="mrow" data-act="meeting" data-id="${m.id}">
    <span class="head"><span class="title">${esc(m.title)}</span><span class="when">${dateLabel(m.date)}</span></span>
    <span class="point">${esc(point || '')}</span>
    <span class="chips"><span class="chip">${esc(kind(m))}${mins(m) ? ' · ' + mins(m) : ''}</span>
      ${open ? `<span class="chip todo">${open} to-do${open > 1 ? 's' : ''}</span>` : ''}
      ${m.private ? '<span class="chip priv">Private</span>' : ''}${m.room === 'large' ? '<span class="chip big">Big room</span>' : ''}</span></button>`;
}
function busyCards() {
  const out = [];
  for (const p of D.pending) out.push(`<div class="busy"><span class="spin"></span><span><span class="t">Redoing: ${esc(p.title)}</span><br><span class="m">${p.why === 'photos' ? 'Adding your photos & notes' : 'Applying your fix'} · usually 3–5 minutes</span></span></div>`);
  for (const p of D.processing) out.push(`<div class="busy"><span class="spin"></span><span><span class="t">New recording · ${esc(p.label)}</span><br><span class="m">${esc(p.stage)}…</span></span></div>`);
  return out.join('');
}
function tldrCard(m) {
  const c = m.tldr;
  const state = m.tldr_state === 'making' ? '<span class="note">TL;DR being written…</span>' : m.tldr_state === 'updating' ? '<span class="note">updating…</span>' : '';
  const todos = m.todos;
  return `<div class="tldr">
    <section><p class="label">The point ${state}</p><p class="point">${esc(c ? c.point : m.summary || 'No summary yet.')}</p></section>
    ${c && c.matters.length ? `<section><h3>What matters</h3><ul class="matters">${c.matters.map(x => `<li>${fmt(x.text)} ${tsBtn(m, x.at)}</li>`).join('')}</ul></section>` : ''}
    <section><h3>Your to-dos</h3>${todos.length ? `<div class="list">${todos.map(t => todoRow(t, false, true)).join('')}</div>` : '<p class="empty">Nothing for you from this one.</p>'}</section>
    ${m.waiting.filter(w => !w.handled).length ? `<section><h3>Waiting on others</h3><div class="list">${m.waiting.filter(w => !w.handled).map(w => waitRow(w)).join('')}</div></section>` : ''}
  </div>`;
}

// ------------------------------------------------------------ views
const VIEWS = {
  home() {
    const hr = new Date().getHours();
    const hi = hr < 12 ? 'Good morning' : hr < 17 ? 'Good afternoon' : 'Good evening';
    const byDate = (a, b) => M(b.meeting).date.localeCompare(M(a.meeting).date);
    const open = D.todos.filter(t => !t.done && t.kind === 'mine').sort(byDate);
    const handoff = D.todos.filter(t => !t.done && t.kind === 'delegate').sort(byDate);
    const recentDone = D.todos.filter(t => t.done && M(t.meeting).age <= 14);
    const shown = S.showAllTodos ? open : open.slice(0, 6);
    const w = D.waiting;
    const h = D.health;
    const hl = h.failed ? `<span class="dot warn"></span>${h.failed} recording${h.failed > 1 ? 's' : ''} failed. Check your Mac.` :
      `<span class="dot"></span>Pipeline running${h.last_note ? ' · last note ' + ago(h.last_note) : ''}`;
    return `<div class="col">
      <p class="sub" style="margin-top:12px">${new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</p>
      <h1>${hi}${D.me.first ? ', ' + esc(D.me.first) : ''}</h1>
      <span class="health">${hl}</span>
      ${offline ? `<div class="offline">Offline. Showing the copy saved ${ago(D.generated)}.</div>` : ''}
      <form class="search" id="searchForm" role="search">${ICON.search}<input id="searchInput" type="search" placeholder="Search meetings" value="${esc(S.q)}" autocomplete="off" aria-label="Search meetings"></form>
      ${S.results ? searchResults() : `
      ${busyCards()}
      <h2>Your to-dos <span class="n">${open.length}</span></h2>
      <div class="list">${shown.map(t => todoRow(t, true)).join('') || '<p class="empty" style="padding:12px 0">All clear.</p>'}</div>
      ${open.length > shown.length ? `<button class="showmore" data-act="moretodos">Show all ${open.length}</button>` : ''}
      ${handoff.length ? `<button class="showmore" data-act="showhandoff">${S.showHandoff ? 'Hide' : 'Show'} ${handoff.length} to hand off</button>${S.showHandoff ? `<p class="sub">Tasks from meetings that nobody took. Assign them or tick them off.</p><div class="list">${handoff.map(t => todoRow(t, true)).join('')}</div>` : ''}` : ''}
      ${recentDone.length ? `<button class="showmore" data-act="showdone">${S.showDone ? 'Hide' : 'Show'} done (${recentDone.length})</button>${S.showDone ? `<div class="list">${recentDone.map(t => todoRow(t, true)).join('')}</div>` : ''}` : ''}
      ${w.length ? `<h2>Waiting on others <span class="n">${w.length}</span></h2><div class="list">${w.slice(0, 5).map(x => waitRow(x, true)).join('')}</div>
        ${w.length > 5 ? `<button class="showmore" data-act="tab" data-id="people">See everyone in People</button>` : ''}` : ''}
      <h2>Recent meetings</h2>
      <div>${D.meetings.slice(0, 12).map(mRow).join('')}</div>
      ${D.meetings.length > 12 ? `<button class="showmore" data-act="tab" data-id="week">See them by week</button>` : ''}`}
    </div>`;
  },
  week() {
    const recent = D.meetings.filter(m => m.age <= 6);
    const list = recent.length ? recent : D.meetings.slice(0, 5);
    let last = '';
    const cards = list.map(m => {
      const day = m.date !== last; last = m.date;
      const c = m.tldr;
      return `${day ? `<p class="day">${dateLabel(m.date, true)}</p>` : ''}<div class="tldr wcard">
        <button class="wt" data-act="meeting" data-id="${m.id}">${esc(m.title)}</button>
        <div class="chips" style="margin-bottom:12px"><span class="chip">${esc(kind(m))}${mins(m) ? ' · ' + mins(m) : ''}</span>${m.private ? '<span class="chip priv">Private</span>' : ''}${m.room === 'large' ? '<span class="chip big">Big room</span>' : ''}</div>
        <p class="wp">${esc(c ? c.point : m.summary)}</p>
        ${c ? `<ul class="matters">${c.matters.map(x => `<li>${fmt(x.text)}</li>`).join('')}</ul>` : ''}
        <button class="linkish" style="margin-top:14px" data-act="meeting" data-id="${m.id}">Open meeting →</button></div>`;
    }).join('');
    return `<div class="col"><h1 style="margin-top:14px">This week</h1>
      <p class="sub">${recent.length ? `${recent.length} meeting${recent.length > 1 ? 's' : ''} in the last 7 days · about ${Math.max(1, Math.round(recent.length / 3))} min to read` : 'No meetings in the last 7 days. Here are the latest.'}</p>
      ${cards}
      ${D.meetings.length > list.length ? `<h2>Older</h2><div>${D.meetings.slice(list.length).map(mRow).join('')}</div>` : ''}</div>`;
  },
  people() {
    const withOpen = D.people.filter(p => p.theyOwe.length || p.youOwe.length);
    const rest = D.people.filter(p => !(p.theyOwe.length || p.youOwe.length));
    const row = p => {
      const n = p.theyOwe.length + p.youOwe.length;
      return `<button class="row" data-act="person" data-id="${esc(p.name)}"><span class="avatar">${esc(initials(p.name))}</span><span class="body"><span class="t">${esc(p.name)}</span><br><span class="m">${esc(p.role)}</span></span><span class="right">${n ? n + ' open' : p.last ? dateLabel(p.last) : ''}</span></button>`;
    };
    return `<div class="col"><h1 style="margin-top:14px">People</h1><p class="sub">What’s open between you and each person</p>
      ${withOpen.length ? `<h2>Something open</h2><div class="list">${withOpen.map(row).join('')}</div>` : ''}
      ${rest.length ? `<h2>Everyone else you’ve met with</h2><div class="list">${rest.map(row).join('')}</div>` : ''}</div>`;
  },
  ask() {
    const a = S.ask;
    const top = D.people.find(p => p.theyOwe.length);
    const recentTitle = D.meetings.find(m => !m.private);
    const sugg = ['What’s still open from last week?', top ? `What did ${top.short} say they’d do?` : null,
      recentTitle ? `What were the main points of the ${recentTitle.title.split(/[-—:]/)[0].trim()}?` : null].filter(Boolean);
    let ans = '';
    if (a) {
      if (a.state === 'running') ans = `<div class="answer tldr"><p class="q">${esc(a.q)}</p><p class="thinking">Reading your meetings… this takes about 30 seconds.</p></div>`;
      else if (a.state === 'error') ans = `<div class="answer tldr"><p class="q">${esc(a.q)}</p><p class="err">${esc(a.error)}</p></div>`;
      else {
        const src = (a.sources || []).map(t => { const m = D.meetings.find(x => x.title === t);
          return m ? `<button data-act="meeting" data-id="${m.id}">${esc(m.title)} · ${dateLabel(m.date)}</button>` : `<span>${esc(t)}</span>`; }).join('');
        ans = `<div class="answer tldr"><p class="q">${esc(a.q)}</p><p class="a">${fmt(a.answer)}</p>${src ? `<h3>From</h3><div class="src">${src}</div>` : ''}</div>`;
      }
    }
    return `<div class="col"><h1 style="margin-top:14px">Ask</h1><p class="sub">Ask anything. Answers come only from your meetings.</p>
      <form class="askbox" id="askForm"><input id="askInput" placeholder="What did we decide about…" autocomplete="off" aria-label="Your question"><button class="btn primary" type="submit">Ask</button></form>
      <div class="sugg">${sugg.map(q => `<button data-act="askq" data-q="${esc(q)}">${esc(q)}</button>`).join('')}</div>${ans}</div>`;
  },
  meeting() {
    const m = M(S.id);
    if (!m) return `<div class="col"><div class="top"><button class="back" data-act="back">${ICON.back}Back</button></div><p class="loading">This meeting is being redone. It’ll be back in a few minutes.</p></div>`;
    const ppl = m.people.map(p => p.known && P(p.name) ? `<button data-act="person" data-id="${esc(p.name)}">${esc(p.name)}</button>` : `<span>${esc(p.name)}</span>`).join('');
    const body = bodies[m.id];
    return `<div class="col">
      <div class="top"><button class="back" data-act="back">${ICON.back}Back</button></div>
      <h1 class="m">${esc(m.title)}</h1>
      <div class="meta"><span>${dateLabel(m.date, true)}${m.time ? ', ' + esc(m.time) : ''}</span>${mins(m) ? `<span>${mins(m)}</span>` : ''}<span>${esc(kind(m))}</span></div>
      ${ppl ? `<div class="pchips">${ppl}</div>` : ''}
      ${m.private ? `<div class="bar priv">${ICON.lock}Private. Never emailed or turned into a recap.</div>` : ''}
      ${m.room === 'large' ? `<div class="bar big">${ICON.people}Big room. Names only where the recording makes it certain.</div>` : ''}
      ${tldrCard(m)}
      ${m.photos && m.photos.length ? `<div class="photos">${m.photos.map(f => `<a href="/api/photo/${m.id}/${f}" target="_blank" rel="noopener"><img src="/api/photo/${m.id}/${f}" alt="Photo from the meeting" loading="lazy"></a>`).join('')}</div>` : ''}
      <div class="actions">
        ${m.has_audio ? `<button class="btn" data-act="listen" data-id="${m.id}">${ICON.speaker}Listen</button>` : ''}
        <button class="btn" data-act="add" data-id="${m.id}">${ICON.camera}Add photos &amp; notes</button>
        <button class="btn" data-act="fix" data-id="${m.id}">${ICON.pen}Fix this note</button>
      </div>
      <details class="full" id="full"><summary>Read the full note <span class="chev">${ICON.chev}</span></summary>
        <div class="note">${body ? MD.render(body, D.roster.map(r => r.name)) : '<p class="empty">Loading…</p>'}</div></details>
      <button class="del" data-act="askdel" data-id="${m.id}">Delete this meeting</button>
    </div>`;
  },
  person() {
    const p = P(S.id);
    if (!p) return `<div class="col"><div class="top"><button class="back" data-act="back">${ICON.back}Back</button></div><p class="loading">Nothing on file for ${esc(S.id)} yet.</p></div>`;
    const owe = p.youOwe.map(T).filter(Boolean);
    return `<div class="col">
      <div class="top"><button class="back" data-act="back">${ICON.back}Back</button></div>
      <div class="phead"><span class="avatar">${esc(initials(p.name))}</span><div><h1>${esc(p.name)}</h1><p class="sub">${esc(p.role)}${p.last ? ' · last met ' + dateLabel(p.last) : ''}</p></div></div>
      <div class="tldr">
        <section><h3>They owe you</h3>${p.theyOwe.length ? `<div class="list">${p.theyOwe.map(w => waitRow(w, true)).join('')}</div>` : '<p class="empty">Nothing open.</p>'}</section>
        <section><h3>You owe them</h3>${owe.length ? `<div class="list">${owe.map(t => todoRow(t, true)).join('')}</div>` : '<p class="empty">Nothing open.</p>'}</section>
        ${p.bring.length ? `<section><h3>Bring up next time</h3><ul class="matters">${p.bring.map(b => `<li>${esc(b.text)}</li>`).join('')}</ul></section>` : ''}
      </div>
      <h2>Meetings together</h2><div>${p.meetings.map(M).filter(Boolean).map(mRow).join('') || '<p class="empty">None yet.</p>'}</div></div>`;
  }
};

function searchResults() {
  const r = S.results;
  return `<h2>Results <span class="n">${r.length}</span><button class="more" data-act="clearsearch">Clear</button></h2>
    <div>${r.map(x => `<button class="mrow" data-act="meeting" data-id="${x.id}"><span class="head"><span class="title">${esc(x.title)}</span><span class="when">${dateLabel(x.date)}</span></span><span class="point" style="-webkit-line-clamp:3">${esc(x.snippet)}</span></button>`).join('') || '<p class="empty">No meetings mention that.</p>'}</div>`;
}

// ------------------------------------------------------------ render / nav
function render(scroll) {
  if (!D) return;
  const tabs = [['home', 'Home'], ['week', 'This week'], ['people', 'People'], ['ask', 'Ask']];
  const open = D.todos.filter(t => !t.done && t.kind === 'mine').length;
  $('#tabs').innerHTML = '<div class="brand">Meeting Notes</div>' + tabs.map(([k, l]) =>
    `<button class="tab" data-act="tab" data-id="${k}" ${S.tab === k && !S.view ? 'aria-current="page"' : ''}><span class="i">${ICON[k]}${k === 'home' && open ? `<span class="badge">${open}</span>` : ''}</span>${l}</button>`).join('');
  const wasOpen = !!document.querySelector('#full[open]');
  $('#main').innerHTML = VIEWS[S.view || S.tab]();
  if (wasOpen && !scroll && $('#full')) $('#full').open = true;
  if (scroll) window.scrollTo(0, 0);
}
function go(view, id) {
  stack.push({ tab: S.tab, view: S.view, id: S.id, y: window.scrollY });
  S.view = view; S.id = id;
  render(true);
  if (view === 'meeting') loadBody(id);
  try { history.pushState({ d: stack.length }, ''); } catch (e) {}
}
function back() {
  const p = stack.pop() || { tab: S.tab, view: null, id: null, y: 0 };
  Object.assign(S, { tab: p.tab, view: p.view, id: p.id });
  render(); window.scrollTo(0, p.y || 0);
}
window.addEventListener('popstate', () => { if (stack.length) back(); });

async function loadBody(id) {
  if (bodies[id]) return;
  try {
    const d = await api('/api/meeting/' + id);
    bodies[id] = d.body;
    try { localStorage.setItem('body:' + id, d.body); } catch (e) {}
  } catch (e) {
    try { bodies[id] = localStorage.getItem('body:' + id) || ''; } catch (e2) {}
  }
  if (S.view === 'meeting' && S.id === id) render();
}

function toast(msg) { const t = $('#toast'); t.textContent = msg; t.hidden = false; clearTimeout(toast.h); toast.h = setTimeout(() => t.hidden = true, 3200); }

// ------------------------------------------------------------ audio player
const audio = $('#audio');
let playing = null;               // meeting id
function updPlayer() {
  $('#pPlay').innerHTML = audio.paused ? ICON.play : ICON.pause;
  const d = audio.duration || 0, c = audio.currentTime || 0;
  if (d) { $('#pSeek').max = Math.floor(d); $('#pSeek').value = Math.floor(c);
    const f = s => { s = Math.floor(s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60; return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0'); };
    $('#pTime').textContent = f(c) + ' / ' + f(d); }
}
function listen(id, at) {
  const m = M(id);
  if (!m) return;
  $('#player').hidden = false; document.body.classList.add('playing');
  $('#pTitle').textContent = m.title;
  const start = at ? toSecs(at) : 0;
  if (playing !== id) {
    playing = id;
    $('#pTime').textContent = 'Getting the audio ready… (long meetings take a few seconds)';
    audio.src = '/api/audio/' + id + '.m4a';
    audio.addEventListener('loadedmetadata', function once() { audio.removeEventListener('loadedmetadata', once); audio.currentTime = start; audio.play().catch(() => {}); });
    audio.load();
  } else { audio.currentTime = start; audio.play().catch(() => {}); }
  updPlayer();
}
['timeupdate', 'play', 'pause', 'loadedmetadata'].forEach(e => audio.addEventListener(e, updPlayer));
audio.addEventListener('error', () => { if (playing) $('#pTime').textContent = 'Couldn’t load the audio.'; });
$('#pPlay').addEventListener('click', () => audio.paused ? audio.play().catch(() => {}) : audio.pause());
$('#pSeek').addEventListener('input', e => { audio.currentTime = +e.target.value; });
$('#pClose').addEventListener('click', () => { audio.pause(); $('#player').hidden = true; document.body.classList.remove('playing'); });

// ------------------------------------------------------------ sheets
function sheet(html) {
  $('#sheetRoot').innerHTML = `<div class="scrim" data-act="scrim"><div class="sheet" role="dialog" aria-modal="true"><div class="grab"></div><button class="x" data-act="close" aria-label="Close">×</button>${html}</div></div>`;
  document.documentElement.classList.add('locked');
}
function closeSheet() { $('#sheetRoot').innerHTML = ''; document.documentElement.classList.remove('locked'); }

// Swipe the sheet down to close it (only when it's scrolled to the top, so its own content still scrolls).
let drag = null;
document.addEventListener('touchstart', e => {
  const sh = e.target.closest('.sheet');
  drag = sh && sh.scrollTop <= 0 && !e.target.closest('textarea,input') ? { sh, y0: e.touches[0].clientY, dy: 0 } : null;
}, { passive: true });
document.addEventListener('touchmove', e => {
  if (!drag) { if (document.querySelector('.scrim') && !e.target.closest('.sheet')) e.preventDefault(); return; }
  drag.dy = e.touches[0].clientY - drag.y0;
  if (drag.dy > 0) { e.preventDefault(); drag.sh.style.transition = 'none'; drag.sh.style.transform = `translateY(${drag.dy}px)`; }
}, { passive: false });
document.addEventListener('touchend', () => {
  if (!drag) return;
  const { sh, dy } = drag; drag = null;
  if (dy > 90) { closeSheet(); return; }
  sh.style.transition = 'transform .18s ease-out'; sh.style.transform = '';
});

function fixSheet(id) {
  const m = M(id);
  sheet(`<h3>Fix this note</h3><p class="sub">Say what’s wrong in plain words. The note gets redone with your fix, and the fix sticks if it’s ever redone again.</p>
    <div class="starters">${['Someone’s name is wrong:', 'Was there, but missing:', 'Wasn’t there:', 'That to-do isn’t mine:', 'Missed a decision:', 'Misheard word:'].map(s => `<button data-act="starter" data-s="${esc(s)}">${esc(s.replace(':', ''))}</button>`).join('')}</div>
    <textarea id="fixText" placeholder="e.g. Speaker 3 was Dana Okafor, and she was in the room."></textarea>
    <p class="err" id="fErr" hidden></p>
    <div class="foot"><button class="btn" data-act="close">Cancel</button><button class="btn primary" data-act="saveFix" data-id="${m.id}">Redo note</button></div>`);
}

// Photos are shrunk on the phone (long side 2000px, JPEG) so uploads stay small over cell data.
let picked = [];
function addSheet(id) {
  picked = [];
  sheet(`<h3>Add photos &amp; notes</h3><p class="sub">Whiteboards, slides, handouts, or your own notes. The text in photos is read on your Mac and the note is redone with it. Photos stay on your Mac.</p>
    <label class="btn pick">${ICON.camera}Choose photos<input type="file" id="pickPhotos" accept="image/*" multiple hidden></label>
    <div class="thumbs" id="thumbs"></div>
    <textarea id="addText" placeholder="Your own notes from the meeting (optional)"></textarea>
    <p class="err" id="aErr" hidden></p>
    <div class="foot"><button class="btn" data-act="close">Cancel</button><button class="btn primary" data-act="saveAdd" data-id="${id}">Add &amp; redo note</button></div>`);
}
function shrink(file) {
  return new Promise((res, rej) => {
    const url = URL.createObjectURL(file), img = new Image();
    img.onload = () => {
      const k = Math.min(1, 2000 / Math.max(img.naturalWidth, img.naturalHeight));
      const c = document.createElement('canvas');
      c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url); res(c.toDataURL('image/jpeg', 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); rej(new Error('Couldn’t open ' + file.name)); };
    img.src = url;
  });
}
document.addEventListener('change', async e => {
  if (e.target.id !== 'pickPhotos') return;
  for (const f of [...e.target.files].slice(0, 12 - picked.length)) {
    try { picked.push(await shrink(f)); } catch (err) { toast(err.message); }
  }
  e.target.value = '';
  $('#thumbs').innerHTML = picked.map((u, i) => `<button data-act="unpick" data-i="${i}" aria-label="Remove photo"><img src="${u}" alt=""><span>×</span></button>`).join('');
});

// ------------------------------------------------------------ events
document.addEventListener('click', async e => {
  const el = e.target.closest('[data-act]'); if (!el) return;
  const a = el.dataset.act, id = el.dataset.id;
  if (el.tagName === 'A') e.preventDefault();
  if (a === 'scrim') { if (e.target === el) closeSheet(); return; }
  switch (a) {
    case 'tab': stack.length = 0; S.tab = id; S.view = null; S.id = null; render(true); break;
    case 'meeting': closeSheet(); go('meeting', id); break;
    case 'person': closeSheet(); go('person', id); break;
    case 'back': back(); break;
    case 'moretodos': S.showAllTodos = true; render(); break;
    case 'showhandoff': S.showHandoff = !S.showHandoff; render(); break;
    case 'showdone': S.showDone = !S.showDone; render(); break;
    case 'clearsearch': S.q = ''; S.results = null; render(); break;
    case 'todo': {
      const t = T(id); if (!t) return;
      const y = window.scrollY; t.done = !t.done;
      D.meetings.forEach(m => m.todos.forEach(x => { if (x.id === id) x.done = t.done; }));
      render(); window.scrollTo(0, y);
      try { await api('/api/todo', { id, done: t.done }); if (t.done) toast(D.reminders ? 'Done. Checked off in Reminders too.' : 'Done.'); }
      catch (err) { t.done = !t.done; render(); toast(err.message); }
      break;
    }
    case 'handled': {
      D.waiting = D.waiting.filter(w => w.key !== id);
      D.meetings.forEach(m => m.waiting.forEach(w => { if (w.key === id) w.handled = true; }));
      D.people.forEach(p => p.theyOwe = p.theyOwe.filter(w => w.key !== id));
      const y = window.scrollY; render(); window.scrollTo(0, y);
      api('/api/waiting/handled', { key: id }).catch(err => toast(err.message));
      break;
    }
    case 'ts': listen(id, el.dataset.t); break;
    case 'listen': listen(id, null); break;
    case 'fix': fixSheet(id); break;
    case 'add': addSheet(id); break;
    case 'askdel': {
      const m = M(id);
      sheet(`<h3>Delete this meeting?</h3><p class="sub">“${esc(m.title)}” and its recording, transcript, email copy and photos are moved to an archive folder on your Mac. Nothing is lost for good, but it’s gone from the app.</p>
        <p class="err" id="dErr" hidden></p>
        <div class="foot"><button class="btn" data-act="close">Cancel</button><button class="btn danger" data-act="dodel" data-id="${id}">Delete</button></div>`);
      break;
    }
    case 'dodel': {
      el.disabled = true;
      try {
        await api('/api/delete', { id });
        closeSheet(); stack.length = 0; S.view = null; S.tab = 'home';
        toast('Deleted.'); refresh();
      } catch (err) { el.disabled = false; const x = $('#dErr'); x.textContent = err.message; x.hidden = false; }
      break;
    }
    case 'unpick': picked.splice(+el.dataset.i, 1); el.remove(); $('#thumbs').querySelectorAll('[data-act="unpick"]').forEach((b, i) => b.dataset.i = i); break;
    case 'saveAdd': {
      const text = $('#addText').value.trim();
      if (!text && !picked.length) { const x = $('#aErr'); x.textContent = 'Choose a photo or type a note first.'; x.hidden = false; break; }
      el.disabled = true; el.textContent = picked.length ? 'Sending photos…' : 'Sending…';
      try {
        const r = await api('/api/add', { id, text, photos: picked });
        closeSheet(); picked = [];
        if (r.redo) { stack.length = 0; S.view = null; S.tab = 'home'; toast('Got it. The note is being redone with your additions. Usually 3–5 minutes.'); }
        else toast('Photos saved. No text in them to add to the note.');
        refresh();
      } catch (err) { el.disabled = false; el.textContent = 'Add & redo note'; const x = $('#aErr'); x.textContent = err.message; x.hidden = false; }
      break;
    }
    case 'close': closeSheet(); break;
    case 'starter': { const t = $('#fixText'); t.value = (t.value ? t.value + '\n' : '') + el.dataset.s + ' '; t.focus(); break; }
    case 'saveFix': {
      const v = $('#fixText').value.trim();
      if (!v) { $('#fixText').focus(); return; }
      el.disabled = true;
      try {
        await api('/api/fix', { id, text: v });
        closeSheet(); stack.length = 0; S.view = null; S.tab = 'home';
        toast('Got it. The note is being redone with your fix. Usually 3–5 minutes.');
        refresh();
      } catch (err) { el.disabled = false; const x = $('#fErr'); x.textContent = err.message; x.hidden = false; }
      break;
    }
    case 'askq': doAsk(el.dataset.q); break;
  }
});
document.addEventListener('toggle', e => { if (e.target.id === 'full' && e.target.open && S.view === 'meeting') loadBody(S.id); }, true);
document.addEventListener('submit', async e => {
  e.preventDefault();
  if (e.target.id === 'askForm') { const v = $('#askInput').value.trim(); if (v) doAsk(v); }
  if (e.target.id === 'searchForm') {
    const q = $('#searchInput').value.trim(); S.q = q;
    if (!q) { S.results = null; render(); return; }
    try { S.results = await api('/api/search?q=' + encodeURIComponent(q)); } catch (err) { toast(err.message); return; }
    render(); $('#searchInput').blur();
  }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });

async function doAsk(q) {
  S.ask = { q, state: 'running' }; render();
  try {
    const { job } = await api('/api/ask', { q });
    const poll = async () => {
      if (!S.ask || S.ask.q !== q) return;
      try {
        const j = await api('/api/ask/' + job);
        if (j.state === 'running') return setTimeout(poll, 2000);
        S.ask = j; if (S.tab === 'ask' && !S.view) render();
      } catch (err) { S.ask = { q, state: 'error', error: err.message }; render(); }
    };
    setTimeout(poll, 2000);
  } catch (err) { S.ask = { q, state: 'error', error: err.message }; render(); }
}

// keep fresh: on open, when coming back to the app, and every minute while it's on screen
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(true); });
setInterval(() => { if (!document.hidden) refresh(true); }, 60000);
if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('/sw.js').catch(() => {});
const cached = loadCopy();
if (cached) { D = cached; offline = true; render(); }
refresh();
