/* Gaffer 2.0 — local FPL assistant. Read-only: nothing here ever changes a team. */
const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
const el = (t, c, h) => { const n = document.createElement(t); if (c) n.className = c; if (h !== undefined) n.innerHTML = h; return n; };
const money = v => '£' + Number(v).toFixed(1);
const nf = v => v == null ? '—' : Number(v).toLocaleString();
const fdrTag = d => `<span class="fdr fdr${d}">${d}</span>`;
const formFg = f => f >= 7 ? 'var(--accent)' : f >= 3 ? 'var(--text)' : 'var(--warn)';
const oppText = p => p.fixtures_gw.length
  ? p.fixtures_gw.map(f => `${f.opponent} ${f.home ? 'H' : 'A'}`).join(', ')
  : 'BLANK';

const NAV = [
  ['squad',     'Squad',     '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/>'],
  ['transfers', 'Transfers', '<path d="M4 8h13l-3-3M20 16H7l3 3"/>'],
  ['rebuild',   'Rebuild',   '<path d="M4 20V9M10 20V4M16 20v-7M22 20H2"/>'],
  ['fixtures',  'Fixtures',  '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>'],
  ['league',    'League',    '<path d="M6 21V7l6-4 6 4v14M6 12h12M6 17h12"/>'],
  ['settings',  'Settings',  '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>'],
];

const DEFAULT_TOGGLES = {
  fdr: true, flagsFirst: true, hideBlanks: false, monoNumbers: true, confirmLeave: false,
};

const S = {
  teamId: null, team: null, season: null, view: 'squad',
  league: null, leagueId: null, rebuild: null,
  out: null, inIdx: 0, bench: 19, locked: new Set(),
  toggles: { ...DEFAULT_TOGGLES }, tick: null,
  swaps: {},          // { outPlayerId: inPlayerId } — transfers FPL hasn't published
  editing: false,     // team-edit mode
  draft: null,        // { xi:[ids], bench:[ids], captain, vice } while editing
  picked: null,       // player selected for a swap
  dirty: false,
};

function curGw() { return S.season ? S.season.next_gw : 0; }
async function loadSwaps() {
  try { S.swaps = await api(`/api/swaps?team=${S.teamId}&gw=${curGw()}`) || {}; }
  catch { S.swaps = {}; }
}
function swapQuery() {
  return Object.entries(S.swaps).map(([o, i]) => `swap=${o}:${i}`).join('&');
}

/* ---------------- storage ---------------- */
// Preferences live on disk, served by the app's own process. The window's
// localStorage is wiped between launches, so it is only a warm cache here.
let PREFS = { team_id: null, recents: [], toggles: {}, bench_budget: 19.0, swaps: {} };

const store = {
  get(k, d) { const v = PREFS[k]; return v === undefined || v === null ? d : v; },
  set(k, v) {
    PREFS[k] = v;
    fetch('/api/prefs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ [k]: v }) }).catch(() => {});
  },
  del(k) { this.set(k, Array.isArray(PREFS[k]) ? [] : null); },
};

async function loadPrefs() {
  try { PREFS = { ...PREFS, ...(await api('/api/prefs')) }; } catch {}
}

async function api(path) {
  const r = await fetch(path);
  const b = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok) throw new Error(b.error || `HTTP ${r.status}`);
  return b;
}
const busy = (on, m) => { $('#loading').hidden = !on; if (m) $('#loadmsg').textContent = m; };
const fail = m => { const e = $('#err'); e.hidden = !m; e.textContent = m || ''; };

/* ---------------- boot ---------------- */
let ACCT = { available: false, signed_in: false, email: null, team_id: null };

async function post(path, body) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(body || {}) });
  const b = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, body: b };
}

function showPane(which) {
  $('#pane-signin').hidden = which !== 'signin';
  $('#pane-team').hidden = which !== 'team';
}
function signinErr(m) { const e = $('#signinerr'); e.hidden = !m; e.textContent = m || ''; }

(async function init() {
  await loadPrefs();
  S.toggles = { ...DEFAULT_TOGGLES, ...store.get('toggles', {}) };
  S.bench = store.get('bench_budget', 19);

  $('#go').addEventListener('click', () => load($('#tid').value.trim()));
  $('#tid').addEventListener('keydown', e => { if (e.key === 'Enter') load(e.target.value.trim()); });
  wireSignin();
  paintRecents();

  try {
    S.season = await api('/api/season');
  } catch (e) {
    $('#enterr').hidden = false;
    $('#enterr').textContent = 'Could not reach the FPL API. Check your connection and reopen. (' + e.message + ')';
    return;
  }

  try { ACCT = await api('/api/account/me'); } catch { ACCT = { available: false, signed_in: false }; }
  // Only advertise sign-in when an account service is actually configured.
  const offer = $('#offer-signin');
  if (offer) offer.hidden = !(ACCT.available && !ACCT.signed_in);

  // Team ID first, always. A new user can be looking at their squad seconds
  // after opening the app, with no account and no server to depend on.
  // Signing in is optional and offered from here and from Settings.
  showPane('team');
  const saved = ACCT.team_id || store.get('team_id', null);
  if (saved) { $('#tid').value = saved; return load(saved); }
  $('#tid').focus();
})();

function wireSignin() {
  const emailStep = () => { $('#step-email').hidden = false; $('#step-code').hidden = true; signinErr(''); };

  $('#sendcode').addEventListener('click', sendCode);
  $('#em').addEventListener('keydown', e => { if (e.key === 'Enter') sendCode(); });
  $('#resend').addEventListener('click', sendCode);
  $('#backemail').addEventListener('click', emailStep);
  $('#verifycode').addEventListener('click', verify);
  $('#code').addEventListener('keydown', e => { if (e.key === 'Enter') verify(); });
  $('#code').addEventListener('input', e => {
    e.target.value = e.target.value.replace(/\D/g, '').slice(0, 6);
    if (e.target.value.length === 6) verify();
  });
  $('#skipsignin').addEventListener('click', () => { showPane('team'); $('#tid').focus(); });
  const gs = $('#gosignin');
  if (gs) gs.addEventListener('click', () => { showPane('signin'); $('#em').focus(); });

  async function sendCode() {
    const email = $('#em').value.trim();
    if (!email.includes('@')) return signinErr('Enter a valid email address.');
    signinErr(''); busy(true, 'Sending your code…');
    const r = await post('/api/account/request', { email });
    busy(false);
    if (!r.ok) return signinErr(r.body.error || 'Could not send that code.');
    $('#sent-to').textContent = email;
    $('#step-email').hidden = true; $('#step-code').hidden = false;
    $('#code').value = ''; $('#code').focus();
  }

  async function verify() {
    const code = $('#code').value.trim();
    if (code.length !== 6) return signinErr('Enter the 6-digit code.');
    signinErr(''); busy(true, 'Checking…');
    const r = await post('/api/account/verify', { email: $('#em').value.trim(), code });
    busy(false);
    if (!r.ok) { $('#code').value = ''; $('#code').focus();
                 return signinErr(r.body.error || 'That code did not work.'); }
    ACCT = { available: true, signed_in: true, email: (r.body.user || {}).email,
             team_id: (r.body.user || {}).team_id };
    showPane('team');
    if (ACCT.team_id) load(ACCT.team_id);
    else $('#tid').focus();
  }
}

function recents() { return store.get('recents', []); }

function remember(entry) {
  const rows = recents().filter(r => r.id !== entry.id);
  rows.unshift({ id: entry.id, name: entry.name, manager: entry.manager });
  store.set('recents', rows.slice(0, 6));
  paintRecents();
}

function paintRecents() {
  const rows = recents();
  const wrap = $('#recents-wrap'), box = $('#recents');
  if (!wrap || !box) return;
  wrap.hidden = !rows.length;
  box.textContent = '';
  rows.forEach(r => {
    const tr = el('div', 'tr');
    tr.innerHTML = `<span><b>${r.name}</b><br><span class="who">${r.manager}</span></span>
                    <span class="mono" style="color:var(--faint)">${r.id}</span>`;
    tr.addEventListener('click', () => { $('#tid').value = r.id; load(r.id); });
    box.append(tr);
  });
}

function goHome() {
  if (S.tick) { clearInterval(S.tick); S.tick = null; }
  store.del('team_id');
  S.team = null; S.teamId = null; S.league = null; S.leagueId = null; S.rebuild = null;
  closeDrawer();
  $('#shell').hidden = true; $('#entry').hidden = false;
  showPane(ACCT.available && !ACCT.signed_in ? 'signin' : 'team');
  $('#enterr').hidden = true;
  $('#tid').value = ''; $('#tid').focus();
  paintRecents();
}

async function load(id) {
  if (!id) { $('#enterr').hidden = false; $('#enterr').textContent = 'Enter your team ID first.'; return; }
  $('#enterr').hidden = true;
  busy(true, 'Loading squad…'); fail('');
  try {
    if (!S.season) S.season = await api('/api/season');
    S.teamId = Number(id);
    await loadSwaps();
    const q = swapQuery();
    S.team = await api('/api/team/' + id + '?gw=' + curGw() + (q ? '&' + q : ''));
    store.set('team_id', S.teamId);
    remember(S.team.entry);
    if (ACCT.signed_in) {
      post('/api/account/team', { team_id: S.teamId })
        .then(() => { ACCT.team_id = S.teamId; })
        .catch(() => {});   // a sync failure must not block the squad loading
    }
    S.out = null; S.inIdx = 0; S.rebuild = null; S.league = null; S.leagueId = null;
    S.locked = new Set();
    $('#entry').hidden = true; $('#shell').hidden = false;
    buildNav(); startClock(); render();
    const sw = $('#switch');
    if (sw && !sw.dataset.wired) { sw.dataset.wired = '1'; sw.addEventListener('click', goHome); }
  } catch (e) {
    if ($('#shell').hidden) { $('#enterr').hidden = false; $('#enterr').textContent = e.message; }
    else fail(e.message);
  } finally { busy(false); }
}

async function reloadTeam() {
  busy(true, 'Recalculating…');
  try {
    const q = swapQuery();
    S.team = await api('/api/team/' + S.teamId + '?gw=' + curGw() + (q ? '&' + q : ''));
    header(); render();
  } catch (e) { fail(e.message); } finally { busy(false); }
}

async function recordSwap(outId, inId) {
  closeDrawer();
  busy(true, 'Saving…');
  try {
    S.swaps = await (await fetch('/api/swaps', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team: S.teamId, gw: curGw(), out: Number(outId), in: Number(inId) }),
    })).json();
  } catch (e) { fail('Could not save that transfer.'); }
  finally { busy(false); }
  reloadTeam();
}

async function undoSwap(outId) {
  try {
    S.swaps = await (await fetch('/api/swaps/clear', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team: S.teamId, gw: curGw(), out: Number(outId) }),
    })).json();
  } catch { fail('Could not undo that.'); }
  reloadTeam();
}

/* ---------------- chrome ---------------- */
function buildNav() {
  const nav = $('#nav'); nav.textContent = '';
  NAV.forEach(([key, label, path]) => {
    const b = el('button', 'nv',
      `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${path}</svg><span>${label}</span>`);
    b.type = 'button'; b.dataset.k = key;
    b.setAttribute('aria-pressed', String(S.view === key));
    b.addEventListener('click', () => { S.view = key; render(); });
    nav.append(b);
  });
}

function startClock() {
  if (S.tick) clearInterval(S.tick);
  const paint = () => {
    const iso = S.season && S.season.deadline_utc;
    $('#dl-gw').textContent = 'Gameweek ' + (S.season ? S.season.next_gw : '—');
    if (!iso) { $('#dl-cd').textContent = '—'; return; }
    let s = Math.max(0, Math.floor((new Date(iso).getTime() - Date.now()) / 1000));
    const d = Math.floor(s / 86400); s -= d * 86400;
    const h = Math.floor(s / 3600); s -= h * 3600;
    const m = Math.floor(s / 60); s -= m * 60;
    const pad = n => String(n).padStart(2, '0');
    $('#dl-cd').textContent = `${d}d ${pad(h)}:${pad(m)}:${pad(s)}`;
    $('#dl-when').textContent = S.season.deadline_local;
    // a gameweek is ~7 days; show how much of the window has elapsed
    const pct = Math.max(0, Math.min(100, 100 - ((d * 86400 + h * 3600 + m * 60 + s) / (7 * 86400)) * 100));
    $('#dl-bar').style.width = pct.toFixed(1) + '%';
  };
  paint(); S.tick = setInterval(paint, 1000);
}

function header() {
  const e = S.team.entry, sq = S.team.squad, gw = S.season.next_gw;
  const H = {
    squad: [(myLeague() || {}).name || 'Fantasy Premier League', e.name,
            `${e.manager} · ${e.region || ''} · ID ${e.id}`],
    transfers: [`Gameweek ${gw}`, 'Transfer planner', 'Model a move before you make it. Nothing is submitted for you.'],
    rebuild: [`Gameweek ${gw} · Wildcard`, 'Rebuild the squad', 'Bench first, then the XI — the order that stops four £4.0m passengers.'],
    fixtures: [`Gameweek ${gw}–${gw + 5}`, 'Fixture ticker', 'Difficulty for every club you currently own.'],
    league: [(S.league && S.league.name) || 'Mini-league', 'Mini-league', 'Click any rival to open their squad.'],
    settings: ['Local install', 'Settings', 'Stored on this machine. Nothing is sent anywhere.'],
  }[S.view];
  $('#h-kick').textContent = H[0]; $('#h-title').textContent = H[1]; $('#h-sub').textContent = H[2];

  const gap = leaderGap();
  const kpis = [
    ['Points', nf(e.overall_points)],
    ['To leader', gap == null ? '—' : (gap > 0 ? '+' + gap : String(gap))],
    ['Squad value', money(sq.value)],
    ['Bank', money(sq.bank)],
  ];
  const box = $('#h-kpis'); box.textContent = '';
  kpis.forEach(([k, v], i) => {
    const d = el('div', 'kpi');
    const colour = (i === 1 && gap != null && gap < 0) ? 'var(--crit)' : (i === 1 && gap > 0) ? 'var(--accent)' : '';
    d.append(el('div', 'v', v), el('div', 'k', k));
    if (colour) d.querySelector('.v').style.color = colour;
    box.append(d);
  });
}

function myLeague() {
  const ls = S.team.leagues || [];
  const small = ls.filter(l => l.size && l.size > 1 && l.size < 500)
                  .sort((a, b) => a.size - b.size);
  return small[0] || ls[0] || null;
}

function leaderGap() {
  const rows = S.league && S.league.rows;
  if (!rows || !rows.length) return null;
  const me = rows.find(r => r.is_me);
  return me ? me.total - rows[0].total : null;
}

/* ---------------- router ---------------- */
function render() {
  $$('#nav .nv').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.k === S.view)));
  header();
  const v = $('#view'); v.textContent = '';
  ({ squad: viewSquad, transfers: viewTransfers, rebuild: viewRebuild,
     fixtures: viewFixtures, league: viewLeague, settings: viewSettings })[S.view](v);
}

/* ---------------- player card ---------------- */
function startEdit() {
  const sq = S.team.squad;
  S.draft = {
    xi: sq.xi.map(p => p.id),
    bench: sq.bench.map(p => p.id),
    captain: (sq.xi.find(p => p.is_captain) || {}).id || null,
    vice: (sq.xi.find(p => p.is_vice) || {}).id || null,
  };
  S.editing = true; S.picked = null; S.dirty = false;
  render();
}

function cancelEdit() {
  S.editing = false; S.draft = null; S.picked = null; S.dirty = false;
  render();
}

function draftPlayer(id) {
  const all = S.team.squad.xi.concat(S.team.squad.bench);
  return all.find(p => p.id === id);
}

/* Formation must stay legal: 1 GK, 3-5 DEF, 2-5 MID, 1-3 FWD. */
function legalXi(ids) {
  const pos = ids.map(id => (draftPlayer(id) || {}).pos);
  const n = p => pos.filter(x => x === p).length;
  return n('GKP') === 1 && n('DEF') >= 3 && n('DEF') <= 5
      && n('MID') >= 2 && n('MID') <= 5 && n('FWD') >= 1 && n('FWD') <= 3;
}

function tapPlayer(id) {
  if (!S.editing) return;
  if (S.picked === null) { S.picked = id; render(); return; }
  if (S.picked === id) { S.picked = null; render(); return; }

  const d = S.draft;
  const a = S.picked, b = id;
  const inXi = x => d.xi.includes(x);
  const swapIn = arr => arr.map(x => x === a ? b : x === b ? a : x);

  if (inXi(a) !== inXi(b)) {
    // one is starting, one is benched — try the substitution
    const nextXi = swapIn(d.xi);
    if (!legalXi(nextXi)) {
      fail('That would leave an illegal formation. FPL needs 1 keeper, 3-5 defenders, 2-5 midfielders and 1-3 forwards.');
      S.picked = null; render(); return;
    }
    d.xi = nextXi; d.bench = swapIn(d.bench);
    // a benched captain isn't allowed
    if (!d.xi.includes(d.captain)) d.captain = null;
    if (!d.xi.includes(d.vice)) d.vice = null;
  } else {
    // both in the same group — reorder (bench order, or cosmetic in the XI)
    d.xi = swapIn(d.xi); d.bench = swapIn(d.bench);
  }
  fail('');
  S.picked = null; S.dirty = true; render();
}

function setArmband(id, which) {
  const d = S.draft;
  if (!d.xi.includes(id)) return;
  if (which === 'captain') {
    if (d.vice === id) d.vice = d.captain;
    d.captain = id;
  } else {
    if (d.captain === id) d.captain = d.vice;
    d.vice = id;
  }
  S.dirty = true; render();
}

async function saveLineup() {
  busy(true, 'Saving your team…');
  try {
    await post('/api/lineup', { team: S.teamId, gw: curGw(), lineup: S.draft });
    S.editing = false; S.draft = null; S.picked = null; S.dirty = false;
    await reloadTeam();
    toast('Team saved. Gaffer will open on this until you change it.');
  } catch (e) { fail(e.message); }
  finally { busy(false); }
}

async function resetLineup() {
  busy(true, 'Reverting…');
  try {
    await post('/api/lineup/clear', { team: S.teamId, gw: curGw() });
    S.editing = false; S.draft = null; S.picked = null; S.dirty = false;
    await reloadTeam();
  } catch (e) { fail(e.message); }
  finally { busy(false); }
}

function toast(msg) {
  const t = el('div', 'toast', msg);
  document.body.append(t);
  setTimeout(() => t.remove(), 4200);
}

function playerCard(p, opts = {}) {
  const b = el('button', 'pc');
  b.type = 'button'; b.dataset.id = p.id;
  const flagged = p.status !== 'ok';
  const badge = p.is_captain ? 'C' : p.is_vice ? 'V' : flagged ? '!' : '';
  const bg = flagged ? 'var(--crit-bg)' : p.is_captain ? 'var(--accent)' : p.is_vice ? '#2A323C' : 'transparent';
  const fg = flagged ? 'var(--crit)' : p.is_captain ? 'var(--accent-ink)' : '#B7C2CE';
  if (flagged) b.style.borderColor = 'var(--crit-bd)';
  else if (p.is_captain) b.style.borderColor = 'var(--lime-bd)';
  if (opts.locked) b.style.borderColor = 'var(--lime-bd)';
  const fx = p.fixtures_gw[0];
  b.innerHTML =
    `<div class="r1"><span class="nm">${p.name}</span>${badge ? `<span class="bdg" style="background:${bg};color:${fg}">${badge}</span>` : ''}</div>
     <div class="r2"><span>${oppText(p)}</span>${fx && S.toggles.fdr ? fdrTag(fx.difficulty) : ''}</div>
     <div class="r3"><span class="pr">${money(p.price)}</span><span style="color:${formFg(p.form)}">${p.form.toFixed(1)}</span></div>`;
  if (S.editing) {
    b.classList.add('editable');
    if (S.picked === p.id) b.classList.add('picked');
    b.addEventListener('click', () => tapPlayer(p.id));
    if ((S.draft.xi || []).includes(p.id)) {
      const arm = el('div', 'armband');
      const c = el('button', 'arm' + (S.draft.captain === p.id ? ' on' : ''), 'C');
      c.title = 'Captain';
      c.addEventListener('click', ev => { ev.stopPropagation(); setArmband(p.id, 'captain'); });
      const v = el('button', 'arm' + (S.draft.vice === p.id ? ' on' : ''), 'V');
      v.title = 'Vice-captain';
      v.addEventListener('click', ev => { ev.stopPropagation(); setArmband(p.id, 'vice'); });
      arm.append(c, v);
      b.append(arm);
    }
  } else {
    b.addEventListener('click', () => openPlayer(p));
  }
  return b;
}

function board(xi, bench, opts = {}) {
  const wrap = el('div', 'board');
  [['GK', 'GKP'], ['DEF', 'DEF'], ['MID', 'MID'], ['FWD', 'FWD']].forEach(([label, pos]) => {
    const line = xi.filter(p => p.pos === pos);
    if (!line.length) return;
    const row = el('div', 'brow');
    row.append(el('span', 'rl', label));
    const cards = el('div', 'cards');
    line.forEach(p => cards.append(playerCard(p, { locked: opts.lockedIds && opts.lockedIds.has(p.id) })));
    row.append(cards); wrap.append(row);
  });
  wrap.append(el('div', 'bench-rule'));
  const row = el('div', 'brow ben');
  row.append(el('span', 'rl', 'BEN'));
  const cards = el('div', 'cards');
  bench.forEach(p => cards.append(playerCard(p, { locked: opts.lockedIds && opts.lockedIds.has(p.id) })));
  row.append(cards); wrap.append(row);
  return wrap;
}

/* ---------------- squad ---------------- */
function viewSquad(root) {
  const sq = S.team.squad;
  const squadAll = sq.xi.concat(sq.bench);
  const byId = id => squadAll.find(p => p.id === id);
  const shownXi = S.editing ? S.draft.xi.map(byId) : sq.xi;
  const shownBench = S.editing ? S.draft.bench.map(byId) : sq.bench;
  const cols = el('div', 'cols');

  const left = el('div');
  const hd = el('div', 'phd');
  hd.append(el('div', 'lbl', `Gameweek ${S.season.next_gw} · ${sq.formation}`));
  if (sq.stale || sq.source !== 'api') hd.append(el('div', 'note-line', 'Recorded by hand — pre-deadline squads aren\'t public'));
  const ctrls = el('div', 'editctl');
  if (!S.editing) {
    const b = el('button', 'btn ghost sm', 'Edit team');
    b.addEventListener('click', startEdit);
    ctrls.append(b);
    if (sq.lineup_saved) {
      const r = el('button', 'linkbtn', 'Revert to FPL');
      r.addEventListener('click', resetLineup);
      ctrls.append(r);
    }
  } else {
    const save = el('button', 'btn sm primary', S.dirty ? 'Save team' : 'Save team');
    save.addEventListener('click', saveLineup);
    const cancel = el('button', 'linkbtn', 'Cancel');
    cancel.addEventListener('click', cancelEdit);
    ctrls.append(save, cancel);
  }
  hd.append(ctrls);
  const rec = sq.swaps || [];
  if (rec.length) {
    const b = el('div', 'swapbar');
    b.innerHTML = `<span class="micro" style="color:var(--accent)">Recorded</span>` +
      rec.map(x => `<span class="swapchip">${x.out} <span class="mono">&rarr;</span> <b>${x.in}</b>
        <button class="undo" data-out="${x.out_id}" title="Undo">&times;</button></span>`).join('');
    left.append(b);
    b.querySelectorAll('.undo').forEach(btn =>
      btn.addEventListener('click', () => undoSwap(btn.dataset.out)));
  }
  // A stale squad with no saved lineup is the single most misleading state the
  // app can be in: every number is live, but the eleven is last week's. Say so
  // loudly rather than in a caption nobody reads.
  if (!S.editing && sq.stale && !sq.lineup_saved) {
    const warn = el('div', 'setupbanner');
    warn.innerHTML =
      '<div class="sb-txt"><b>This is your GW' + sq.gw + ' team, not your GW' + S.season.next_gw + ' one.</b>' +
      '<p>FPL doesn\'t publish a squad before its deadline, so Gaffer can\'t read the eleven, ' +
      'bench order or captain you\'ve set for GW' + S.season.next_gw + '. Set them once and it remembers.</p></div>';
    const go = el('button', 'btn sm primary', 'Set my team');
    go.addEventListener('click', startEdit);
    warn.append(go);
    left.append(warn);
  }
  if (S.editing) {
    const hint = el('div', 'edithint');
    hint.innerHTML = S.picked
      ? 'Now tap the player to swap with <b>' + (draftPlayer(S.picked) || {}).name + '</b>.'
      : 'Tap two players to swap them — bench for starter, or to reorder the bench. '
        + 'Use <b>C</b> and <b>V</b> for the armbands, then Save.';
    left.append(hint);
  }
  left.append(hd, board(shownXi, shownBench));
  cols.append(left);

  const right = el('div', 'stack');

  const insHd = el('div', 'phd');
  insHd.append(el('div', 'lbl', 'What to look at'),
               el('div', 'mono', `<span style="color:var(--faint);font-size:11px">${S.team.advice.length}</span>`));
  const insBox = el('div', 'stack'); insBox.style.gap = '9px';
  if (!S.team.advice.length) {
    insBox.append(el('div', 'empty', 'Nothing to change. The squad is legal, nobody in the XI is flagged, and the bench order is sound.'));
  } else {
    const tone = { critical: 'crit', warning: 'warn', info: 'info' };
    S.team.advice.forEach(a => {
      const d = el('div', 'ins ' + (tone[a.severity] || 'info'));
      d.innerHTML =
        `<div class="top"><span class="micro kind">${a.kind || a.severity}</span><span class="gw">GW${S.season.next_gw}</span></div>
         <h3>${a.title}</h3><p>${a.detail}</p>`;
      insBox.append(d);
    });
  }
  const insWrap = el('div'); insWrap.append(insHd, insBox); right.append(insWrap);

  const lgWrap = el('div');
  const lgHd = el('div', 'phd');
  lgHd.append(el('div', 'lbl', 'Mini-league'));
  const all = el('a', '', 'All →'); all.href = '#';
  all.addEventListener('click', e => { e.preventDefault(); S.view = 'league'; render(); });
  lgHd.append(all);
  lgWrap.append(lgHd);
  const lgBox = el('div', 'tbl'); lgBox.id = 'mini';
  lgBox.append(el('div', 'empty', 'Loading standings…'));
  lgWrap.append(lgBox); right.append(lgWrap);

  right.append(subsPanel());
  cols.append(right); root.append(cols);
  ensureLeague().then(() => paintMini(lgBox)).catch(() => { lgBox.textContent = ''; lgBox.append(el('div', 'empty', 'No mini-league found.')); });
}

async function ensureLeague() {
  if (S.league) return S.league;
  const pick = S.leagueId || (myLeague() || {}).id;
  if (!pick) throw new Error('none');
  S.leagueId = pick;
  S.league = await api(`/api/league/${pick}?team=${S.teamId}`);
  header();
  return S.league;
}

function subsPanel() {
  const subs = S.team.subs || [];
  const order = S.team.bench_order || [];
  const misordered = order.filter(b => b.moved);

  const wrap = el('div');
  const head = el('div', 'phd');
  head.append(el('div', 'lbl', 'Substitutions'));
  head.append(el('div', 'mono', '<span style="color:var(--faint);font-size:11px">' + subs.length + '</span>'));
  wrap.append(head);

  const box = el('div', 'stack'); box.style.gap = '9px';

  if (!subs.length) {
    box.append(el('div', 'ins info',
      '<div class="top"><span class="micro kind">Settled</span></div>' +
      '<h3>Your best eleven is already on the pitch</h3>' +
      '<p>No bench player improves on a starter on form, fixture or fitness.</p>'));
  } else {
    subs.forEach(sub => {
      const tone = { critical: 'crit', warning: 'warn', info: 'info' }[sub.severity] || 'info';
      const label = sub.severity === 'critical' ? 'Do this'
                  : sub.severity === 'warning' ? 'Worth doing' : 'Consider';
      const d = el('div', 'ins ' + tone);
      d.innerHTML =
        '<div class="top"><span class="micro kind">' + label + '</span>' +
        '<span class="gw mono">' + sub.formation_after + '</span></div>' +
        '<h3>' + sub.headline + '</h3>' +
        '<div class="subline">' +
          '<span class="off">' + sub.out_name +
            '<span class="mono">' + sub.out_club + ' · form ' + sub.out_form + ' · fdr ' + sub.out_fdr + '</span></span>' +
          '<span class="mono arrow">&rarr;</span>' +
          '<span class="on">' + sub.in_name +
            '<span class="mono">' + sub.in_club + ' · form ' + sub.in_form + ' · fdr ' + sub.in_fdr + '</span></span>' +
        '</div>' +
        '<ul class="whys">' + sub.reasons.map(r => '<li>' + r + '</li>').join('') + '</ul>';
      box.append(d);
    });
  }

  if (misordered.length) {
    const d = el('div', 'ins warn');
    d.innerHTML =
      '<div class="top"><span class="micro kind">Bench order</span></div>' +
      '<h3>Reorder your bench</h3>' +
      '<p>Bench order only pays out when a starter doesn\'t play, so the likeliest ' +
      'scorer should be first.</p>' +
      '<ol class="benchorder">' + order.map(b =>
        '<li' + (b.moved ? ' class="moved"' : '') + '><b>' + b.name + '</b>' +
        '<span class="mono">' + b.club + ' · form ' + b.form + ' · fdr ' + b.fdr + '</span>' +
        (b.moved ? '<span class="mono was">now ' + b.current_slot + '</span>' : '') +
        '</li>').join('') + '</ol>';
    box.append(d);
  }

  wrap.append(box);
  wrap.append(el('p', 'foot',
    'Gaffer can\'t change your team — make these on the FPL site before the deadline.'));
  return wrap;
}

function paintMini(box) {
  box.textContent = '';
  const th = el('div', 'th'); th.style.gridTemplateColumns = '22px 1fr auto auto';
  th.innerHTML = '<span>#</span><span>Team</span><span class="r">GW</span><span class="r">Total</span>';
  box.append(th);
  S.league.rows.slice(0, 4).forEach(r => {
    const tr = el('div', 'tr' + (r.is_me ? ' me' : ''));
    tr.style.gridTemplateColumns = '22px 1fr auto auto';
    tr.innerHTML = `<span class="mono" style="color:var(--faint)">${r.rank}</span>
      <span style="font-weight:500">${r.name}</span>
      <span class="mono r" style="color:var(--muted)">${r.gw}</span>
      <span class="mono r" style="font-weight:600">${r.total}</span>`;
    tr.style.cursor = 'pointer';
    tr.addEventListener('click', () => load(r.entry));
    box.append(tr);
  });
}

/* ---------------- transfers ---------------- */
function viewTransfers(root) {
  const sq = S.team.squad;
  const all = sq.xi.concat(sq.bench);
  if (!S.out) S.out = (all.find(p => p.status !== 'ok') || all.slice().sort((a, b) => a.form - b.form)[0]).id;
  const out = all.find(p => p.id === S.out) || all[0];

  const grid = el('div', 'tp');

  const left = el('div');
  left.append(el('div', 'lbl', 'Pick who leaves'));
  const list = el('div', 'tbl'); list.style.marginTop = '11px';
  all.forEach(p => {
    const tr = el('div', 'tr' + (p.id === S.out ? ' sel' : ''));
    tr.style.gridTemplateColumns = '30px 1fr auto auto';
    tr.innerHTML = `<span class="mono" style="font-size:9.5px;color:var(--faint)">${p.pos}</span>
      <span style="font-weight:500${p.id === S.out ? ';color:var(--accent)' : ''}">${p.name}</span>
      <span class="mono r" style="color:var(--muted)">${money(p.price)}</span>
      <span class="mono r" style="color:${formFg(p.form)}">${p.form.toFixed(1)}</span>`;
    tr.style.cursor = 'pointer';
    tr.addEventListener('click', () => { S.out = p.id; S.inIdx = 0; render(); });
    list.append(tr);
  });
  left.append(list);
  grid.append(left);

  const right = el('div', 'stack');
  const reps = out.replacements || [];
  const inc = reps[Math.min(S.inIdx, Math.max(0, reps.length - 1))];

  const hdr = el('div', 'xfer');
  if (!inc) {
    hdr.innerHTML = `<div class="lbl">No move clears your rules</div>
      <p style="margin:10px 0 0;color:var(--muted);font-size:12.5px;line-height:1.55">
        Nothing in ${out.pos} improves on <b style="color:var(--text)">${out.name}</b> within
        ${money(out.price)} + ${money(sq.bank)} bank. Every candidate is lower form, flagged,
        unaffordable, or would break the three-per-club limit.</p>`;
  } else {
    const cost = inc.cost, gain = inc.form_delta;
    const verdict = gain >= 7 ? ['good', `Clear upgrade. ${inc.name} is on form ${inc.form} against ${out.form.toFixed(1)} — that gap is worth a transfer on its own.`]
                  : gain >= 3 ? ['marg', `Reasonable, not urgent. ${inc.name} gains you ${gain.toFixed(1)} form for ${cost > 0 ? money(cost) : 'nothing'}. Worth it only if you weren't saving the transfer.`]
                  : ['bad', `Marginal. A ${gain.toFixed(1)} form gain rarely repays a transfer — rolling it is usually better.`];
    hdr.innerHTML =
      `<div class="xrow">
        <div class="xblk"><span class="micro" style="color:var(--crit)">Out</span>
          <div class="nm">${out.name}</div>
          <div class="meta">${out.club} · ${out.pos} · ${money(out.price)} · form ${out.form.toFixed(1)}</div></div>
        <span class="xarrow">→</span>
        <div class="xblk"><span class="micro" style="color:var(--accent)">In</span>
          <div class="nm">${inc.name}</div>
          <div class="meta">${inc.club} · ${inc.pos} · ${money(inc.price)} · form ${inc.form.toFixed(1)}</div></div>
        <div class="xfigs">
          <div class="xfig"><div class="v" style="color:${cost > 0 ? 'var(--crit)' : 'var(--accent)'}">${cost > 0 ? '+' : ''}${money(cost).replace('£', '£')}</div><div class="k">Cost</div></div>
          <div class="xfig"><div class="v" style="color:var(--accent)">+${gain.toFixed(1)}</div><div class="k">Form Δ</div></div>
          <div class="xfig"><div class="v">0</div><div class="k">Hit</div></div>
        </div>
      </div>
      <div class="verdict ${verdict[0]}">${verdict[1]}</div>`;
  }
  right.append(hdr);

  if (reps.length) {
    const box = el('div');
    box.append(el('div', 'lbl', 'Replacements worth the transfer'));
    const t = el('div', 'tbl'); t.style.marginTop = '11px';
    const CG = '1.4fr .7fr .8fr .8fr .9fr 1.1fr';
    const th = el('div', 'th'); th.style.gridTemplateColumns = CG;
    th.innerHTML = '<span>Player</span><span>Club</span><span class="r">Price</span><span class="r">Cost</span><span class="r">Form +</span><span>Next</span>';
    t.append(th);
    reps.forEach((r, i) => {
      const tr = el('div', 'tr' + (i === S.inIdx ? ' sel' : ''));
      tr.style.gridTemplateColumns = CG; tr.style.cursor = 'pointer';
      tr.innerHTML = `<span style="font-weight:600">${r.name}</span>
        <span class="mono" style="color:var(--muted)">${r.club}</span>
        <span class="mono r">${money(r.price)}</span>
        <span class="mono r" style="color:${r.cost > 0 ? 'var(--crit)' : 'var(--muted)'}">${r.cost > 0 ? '+' : ''}${r.cost.toFixed(1)}</span>
        <span class="mono r" style="color:var(--accent);font-weight:600">+${r.form_delta.toFixed(1)}</span>
        <span class="mono" style="font-size:11px">${r.fixture} ${S.toggles.fdr ? fdrTag(r.fdr) : ''}</span>`;
      tr.addEventListener('click', () => { S.inIdx = i; render(); });
      t.append(tr);
    });
    box.append(t);
    box.append(el('p', 'foot', 'Higher form than the outgoing player, fit, affordable, and legal on the three-per-club rule. Nothing is applied automatically — you type it into FPL yourself.'));
    right.append(box);
  }

  grid.append(right); root.append(grid);
}

/* ---------------- rebuild ---------------- */
function viewRebuild(root) {
  const sq = S.team.squad;
  const wrap = el('div', 'stack');

  const panel = el('div', 'panel'); panel.style.padding = '16px 18px';
  const ctl = el('div', 'ctl');
  ctl.innerHTML = `<span class="lbl" style="letter-spacing:.13em">Bench budget</span>
    <input id="bslide" type="range" min="16" max="30" step="0.5" value="${S.bench}">
    <output id="bout" class="mono" style="font-weight:600;min-width:48px">${money(S.bench)}m</output>`;
  const go = el('button', 'btn ghost', 'Build squad');
  go.style.background = 'var(--accent)'; go.style.color = 'var(--accent-ink)'; go.style.borderColor = 'var(--accent)';
  ctl.append(go);
  ctl.append(el('span', 'note-line', `Budget ${money(sq.value + sq.bank)}m`));
  panel.append(ctl);

  const chips = el('div', 'ctl'); chips.style.marginTop = '14px';
  chips.append(el('span', 'lbl', 'Keep'));
  sq.xi.concat(sq.bench).forEach(p => {
    const c = el('button', 'chip', `${p.name} ${money(p.price)}`);
    c.type = 'button'; c.setAttribute('aria-pressed', String(S.locked.has(p.id)));
    c.addEventListener('click', () => {
      S.locked.has(p.id) ? S.locked.delete(p.id) : S.locked.add(p.id);
      c.setAttribute('aria-pressed', String(S.locked.has(p.id)));
    });
    chips.append(c);
  });
  panel.append(chips);
  wrap.append(panel);

  const out = el('div'); out.id = 'rout';
  if (S.rebuild) out.append(rebuildResult(S.rebuild));
  else out.append(el('div', 'empty', 'Lock the players you want to keep, set a bench budget, then build. Nothing is applied — it\'s a plan you type in yourself.'));
  wrap.append(out);
  root.append(wrap);

  $('#bslide').addEventListener('input', e => {
    S.bench = Number(e.target.value); store.set('bench_budget', S.bench);
    $('#bout').textContent = money(S.bench) + 'm';
  });
  go.addEventListener('click', doRebuild);
}

async function doRebuild() {
  fail(''); busy(true, 'Solving for a legal 15…');
  try {
    const q = new URLSearchParams(); q.set('bench', S.bench);
    S.locked.forEach(id => q.append('lock', id));
    S.rebuild = await api(`/api/team/${S.teamId}/rebuild?${q}`);
    const o = $('#rout'); o.textContent = ''; o.append(rebuildResult(S.rebuild));
  } catch (e) { fail(e.message); } finally { busy(false); }
}

function rebuildResult(r) {
  const box = el('div', 'stack');
  const sum = el('div', 'ctl');
  sum.innerHTML = `<span style="font-size:18px;font-weight:600">${r.formation}</span>
    <span class="mono" style="color:var(--muted)">${money(r.cost)}m spent · ${money(r.spare)}m spare</span>
    <span style="color:var(--muted)">Bench Boost ready
      <b class="mono" style="color:${r.bench_ready === 4 ? 'var(--accent)' : 'var(--warn)'}">${r.bench_ready}/4</b></span>`;
  box.append(sum);
  box.append(board(r.xi, r.bench, { lockedIds: new Set(r.xi.concat(r.bench).filter(p => p.locked).map(p => p.id)) }));

  const t = el('div', 'tbl');
  const CG = '1.3fr .9fr 1fr 1fr';
  const th = el('div', 'th'); th.style.gridTemplateColumns = CG;
  th.innerHTML = '<span>Bench</span><span class="r">Minutes</span><span>Next</span><span>Verdict</span>';
  t.append(th);
  r.bench_detail.forEach(b => {
    const tr = el('div', 'tr'); tr.style.gridTemplateColumns = CG;
    tr.innerHTML = `<span><b>${b.name}</b> <span style="color:var(--faint)">${b.club}</span></span>
      <span class="mono r">${b.minutes}′ ${Math.round(b.share * 100)}%</span>
      <span class="mono" style="font-size:11px">${b.fixture} ${S.toggles.fdr ? fdrTag(b.fdr) : ''}</span>
      <span style="color:${b.ok ? 'var(--accent)' : 'var(--crit)'}">${b.verdict}</span>`;
    t.append(tr);
  });
  box.append(t);

  const kv = el('div', 'panel'); kv.style.padding = '14px 16px';
  kv.innerHTML = `<div class="micro" style="color:var(--accent)">Keeps</div>
    <p style="margin:5px 0 0;color:var(--muted);font-size:12.5px">${r.kept.join(', ') || 'none'}</p>
    <div style="height:1px;background:var(--line);margin:12px 0"></div>
    <div class="micro" style="color:var(--crit)">Sells</div>
    <p style="margin:5px 0 0;color:var(--muted);font-size:12.5px">${r.out.join(', ') || 'none'}</p>`;
  box.append(kv);
  return box;
}

/* ---------------- fixtures ---------------- */
async function viewFixtures(root) {
  const owned = new Set(S.team.squad.xi.concat(S.team.squad.bench).map(p => p.club));
  root.append(el('div', 'lbl', 'Clubs you own'));
  const holder = el('div', 'panel'); holder.style.cssText = 'padding:16px 18px;margin-top:11px';
  holder.append(el('div', 'loading', '<span class="spin"></span><span>Loading fixtures…</span>'));
  root.append(holder);
  try {
    const rows = (await api('/api/ticker?n=6')).filter(r => owned.has(r.club));
    holder.textContent = '';
    const gw = S.season.next_gw;
    const grid = el('div', 'tick');
    grid.append(el('span', 'hd', ''));
    for (let i = 0; i < 6; i++) grid.append(el('span', 'hd', 'GW' + (gw + i)));
    grid.append(el('span', 'hd', 'Avg'));
    rows.forEach(r => {
      grid.append(el('span', 'cl', r.club));
      for (let i = 0; i < 6; i++) {
        const f = r.fixtures.find(x => x.gw === gw + i);
        const c = el('span', 'cell ' + (f ? 'fdr' + f.difficulty : 'fdr5'));
        c.innerHTML = f ? `${f.opponent}<br><span style="opacity:.7">${f.home ? 'H' : 'A'}</span>` : 'BLANK';
        grid.append(c);
      }
      const a = el('span', 'avg', r.fdr.toFixed(2));
      a.style.color = r.fdr <= 2.8 ? 'var(--accent)' : r.fdr >= 3.8 ? 'var(--crit)' : 'var(--text)';
      grid.append(a);
    });
    holder.append(grid);
    holder.append(el('p', 'foot', 'Mean difficulty over the next six fixtures. Lime is a good run, red is a bad one. A blank counts as the worst case.'));
  } catch (e) { holder.textContent = ''; holder.append(el('div', 'err', e.message)); }
}

/* ---------------- league ---------------- */
async function viewLeague(root) {
  const holder = el('div');
  holder.append(el('div', 'loading', '<span class="spin"></span><span>Loading standings…</span>'));
  root.append(holder);
  try {
    await ensureLeague();
    holder.textContent = '';
    const t = el('div', 'tbl');
    const CG = '34px 1fr 1fr auto auto auto';
    const th = el('div', 'th'); th.style.gridTemplateColumns = CG;
    th.innerHTML = '<span>#</span><span>Team</span><span>Manager</span><span class="r">GW</span><span class="r">Total</span><span class="r">Move</span>';
    t.append(th);
    S.league.rows.forEach(r => {
      const tr = el('div', 'tr' + (r.is_me ? ' me' : ''));
      tr.style.gridTemplateColumns = CG; tr.style.cursor = 'pointer';
      const mv = r.moved > 0 ? `<span style="color:var(--accent)">▲${r.moved}</span>`
              : r.moved < 0 ? `<span style="color:var(--crit)">▼${-r.moved}</span>` : '—';
      tr.innerHTML = `<span class="mono" style="color:var(--faint)">${r.rank}</span>
        <span style="font-weight:600">${r.name}</span>
        <span style="color:var(--muted)">${r.manager}</span>
        <span class="mono r">${r.gw}</span><span class="mono r" style="font-weight:600">${r.total}</span>
        <span class="mono r">${mv}</span>`;
      tr.addEventListener('click', () => { load(r.entry); S.view = 'squad'; });
      t.append(tr);
    });
    holder.append(t);
    const gap = leaderGap();
    holder.append(el('p', 'foot', gap == null ? 'Click any rival to open their squad.'
      : gap >= 0 ? `You lead by ${gap}. When you're ahead, covering rival differentials protects the lead better than backing your own. Click any rival to see theirs.`
      : `You're ${-gap} behind. When you're chasing, differentials are your friend — you need the variance. Click any rival to see what they own that you don't.`));
  } catch (e) { holder.textContent = ''; holder.append(el('div', 'err', e.message)); }
}

/* ---------------- settings ---------------- */
function viewSettings(root) {
  const p = el('div', 'panel'); p.style.padding = '18px 20px';
  p.append(el('div', 'lbl', 'This install'));
  const idrow = el('div', 'ctl'); idrow.style.margin = '12px 0 4px';
  idrow.innerHTML = `<input id="sid" class="field mono" style="font-size:15px;padding:10px 13px;max-width:220px" value="${S.teamId}">`;
  const save = el('button', 'btn ghost', 'Load this team');
  save.addEventListener('click', () => load($('#sid').value.trim()));
  idrow.append(save);
  p.append(idrow);
  p.append(el('p', 'foot', `${S.team.entry.name} · ${S.team.entry.manager}`));

  const t = el('div', 'panel'); t.style.cssText = 'padding:6px 20px;margin-top:18px';
  const TOG = [
    ['fdr', 'Fixture difficulty chips', 'Show the 1–5 difficulty tag beside every fixture.'],
    ['flagsFirst', 'Sort flags to the top', 'Injuries and doubts lead the insight list.'],
    ['hideBlanks', 'Dim blank gameweeks', 'Fade players whose club has no fixture.'],
    ['monoNumbers', 'Monospaced figures', 'Keep every number tabular so columns line up.'],
    ['confirmLeave', 'Warn before switching team', 'Ask before loading a different entry ID.'],
  ];
  TOG.forEach(([k, label, desc]) => {
    const row = el('div', 'togrow');
    const sw = el('button', 'sw', '<i></i>');
    sw.type = 'button'; sw.setAttribute('aria-pressed', String(!!S.toggles[k]));
    sw.addEventListener('click', () => {
      S.toggles[k] = !S.toggles[k];
      sw.setAttribute('aria-pressed', String(S.toggles[k]));
      store.set('toggles', S.toggles);
    });
    const txt = el('div'); txt.append(el('div', 't', label), el('div', 'd', desc));
    txt.style.flex = '1';
    row.append(txt, sw); t.append(row);
  });

  const a = el('div', 'panel'); a.style.cssText = 'padding:18px 20px;margin-top:18px';
  a.append(el('div', 'lbl', 'Account'));
  if (!ACCT.available) {
    a.append(el('p', 'foot', 'Accounts aren\'t configured for this install. Gaffer works fully signed out — your team ID is remembered on this machine.'));
  } else if (!ACCT.signed_in) {
    a.append(el('p', 'foot', 'Signed out. Sign in to have your team follow you to another machine.'));
    const si = el('button', 'btn ghost', 'Sign in'); si.style.marginTop = '12px';
    si.addEventListener('click', () => { goHome(); showPane('signin'); $('#em').focus(); });
    a.append(si);
  } else {
    const bar = el('div', 'acctbar'); bar.style.margin = '12px 0';
    bar.innerHTML = `<span class="dot"></span><span class="em">${ACCT.email}</span>`;
    a.append(bar);
    a.append(el('p', 'foot', 'Your team ID is saved to this account. We hold your email address and that ID — nothing else.'));
    const row = el('div', 'ctl'); row.style.marginTop = '12px';
    const out = el('button', 'btn ghost', 'Sign out');
    out.addEventListener('click', async () => { await post('/api/account/logout');
      ACCT = { ...ACCT, signed_in: false, email: null, team_id: null }; goHome(); });
    const del = el('button', 'btn ghost', 'Delete account');
    del.style.borderColor = 'var(--crit)'; del.style.color = 'var(--crit)';
    del.addEventListener('click', async () => {
      if (!confirm('Delete your Gaffer account?\n\nYour email address and saved team ID are erased immediately. This cannot be undone.')) return;
      const r = await post('/api/account/delete');
      if (!r.ok) return fail(r.body.error || 'Could not delete the account.');
      ACCT = { ...ACCT, signed_in: false, email: null, team_id: null };
      store.del('team_id'); store.del('recents'); goHome();
    });
    row.append(out, del); a.append(row);
  }

  const c = el('div', 'panel'); c.style.cssText = 'padding:18px 20px;margin-top:18px';
  c.append(el('div', 'lbl', 'Local data'));
  c.append(el('p', 'foot', 'Team ID and preferences are stored in this browser profile only. FPL data is cached for a few minutes to avoid hammering their API.'));
  const clear = el('button', 'btn ghost', 'Forget this machine');
  clear.style.marginTop = '12px';
  clear.addEventListener('click', () => {
    store.del('team_id'); store.del('toggles'); store.del('bench_budget'); store.del('recents');
    S.toggles = { ...DEFAULT_TOGGLES };
    goHome();
  });
  c.append(clear);

  root.append(p, t, a, c);
}

/* ---------------- drawer ---------------- */
async function openPlayer(p) {
  const flagged = p.status !== 'ok';
  $('#dbody').innerHTML =
    `<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
      <div><div class="lbl" style="letter-spacing:.13em">${p.club} · ${p.pos}${p.benched ? ' · bench' : ''}</div>
        <div style="font-size:28px;font-weight:600;letter-spacing:-.02em;margin-top:4px">${p.name}</div></div>
      <button class="btn ghost" id="dx">Close</button>
    </div>
    <div class="dg">
      <div class="b"><div class="k">Price</div><div class="v">${money(p.price)}</div></div>
      <div class="b"><div class="k">Form</div><div class="v" style="color:${formFg(p.form)}">${p.form.toFixed(1)}</div></div>
      <div class="b"><div class="k">Points</div><div class="v">${p.points}</div></div>
      <div class="b"><div class="k">Per game</div><div class="v">${p.ppg ?? '—'}</div></div>
      <div class="b"><div class="k">Minutes</div><div class="v">${p.minutes ?? '—'}</div></div>
      <div class="b"><div class="k">Owned</div><div class="v">${p.selected}%</div></div>
    </div>
    ${flagged ? `<div class="newsbox"><b>${p.status}</b>${p.news ? ' — ' + p.news : ''} · ${p.chance}% chance to play</div>` : ''}
    <div class="lbl" style="margin-top:20px;letter-spacing:.13em">Next five</div>
    <div class="fx5">${p.fixtures_next.map(f => `<span>GW${f.gw} ${f.opponent} ${f.home ? 'H' : 'A'} ${fdrTag(f.difficulty)}</span>`).join('') || '<span>No scheduled fixtures</span>'}</div>
    <div class="lbl" style="margin-top:20px;letter-spacing:.13em">Already transferred this player out?</div>
    <p class="foot" style="margin-top:6px">FPL doesn't publish your squad before a deadline, so record it here and everything recalculates.</p>
    <div class="recwrap">
      <input id="recq" class="srch" type="search" placeholder="Search the ${p.pos} who replaced ${p.name}…" autocomplete="off">
      <div id="recres"></div>
    </div>
    <div class="lbl" style="margin-top:20px;letter-spacing:.13em">Last five gameweeks</div>
    <div id="dhist" class="loading" style="margin-top:9px"><span class="spin"></span><span>Loading…</span></div>
    ${repsTable(p)}`;
  $('#drawer').classList.add('open'); $('#scrim').hidden = false;
  $('#dx').addEventListener('click', closeDrawer);
  wireRecord(p);

  try {
    const h = await api('/api/player/' + p.id);
    const box = $('#dhist'); if (!box) return;
    const rows = h.history.slice(-5);
    if (!rows.length) { box.className = 'empty'; box.textContent = 'No appearances yet this season.'; return; }
    const max = Math.max(4, ...rows.map(r => r.points));
    box.className = 'bars';
    box.innerHTML = rows.map(r => {
      const pct = Math.max(4, (r.points / max) * 100);
      const col = r.points >= 6 ? 'var(--accent)' : r.points >= 3 ? 'var(--panel-3)' : 'var(--line-strong)';
      return `<div class="b" style="height:${pct}%;background:${col}"><b>${r.points}</b></div>`;
    }).join('');
  } catch { const b = $('#dhist'); if (b) { b.className = 'empty'; b.textContent = 'History unavailable.'; } }
}

function wireRecord(p) {
  const box = $('#recq'); if (!box) return;
  const owned = new Set(S.team.squad.xi.concat(S.team.squad.bench).map(x => x.id));
  let t;
  box.addEventListener('input', e => {
    clearTimeout(t);
    const q = e.target.value.trim();
    if (q.length < 2) { $('#recres').textContent = ''; return; }
    t = setTimeout(async () => {
      try {
        const rows = (await api('/api/search?q=' + encodeURIComponent(q)))
          .filter(r => r.pos === p.pos && !owned.has(r.id));
        const box2 = $('#recres'); box2.textContent = '';
        if (!rows.length) {
          box2.innerHTML = `<p class="foot">No ${p.pos} found by that name who isn't already in your squad.</p>`;
          return;
        }
        rows.slice(0, 6).forEach(r => {
          const row = el('button', 'recrow',
            `<span><b>${r.name}</b> <span style="color:var(--faint)">${r.club}</span></span>
             <span class="mono">${money(r.price)}</span>
             <span class="mono" style="color:${formFg(r.form)}">${r.form}</span>`);
          row.type = 'button';
          row.addEventListener('click', () => recordSwap(p.id, r.id));
          box2.append(row);
        });
      } catch (err) { fail(err.message); }
    }, 220);
  });
}

function repsTable(p) {
  if (!p.replacements || !p.replacements.length) {
    return `<div class="lbl" style="margin-top:20px;letter-spacing:.13em">Replacements</div>
      <p class="foot">Nothing in this position clears the rules on the available budget — every candidate is lower form, flagged, unaffordable, or would break the three-per-club limit.</p>`;
  }
  const rows = p.replacements.map(r => `<div class="tr" style="grid-template-columns:1.4fr .8fr .8fr .9fr">
      <span style="font-weight:600">${r.name}</span>
      <span class="mono" style="color:var(--muted)">${money(r.price)}</span>
      <span class="mono r" style="color:${r.cost > 0 ? 'var(--crit)' : 'var(--muted)'}">${r.cost > 0 ? '+' : ''}${r.cost.toFixed(1)}</span>
      <span class="mono r" style="color:var(--accent);font-weight:600">+${r.form_delta.toFixed(1)}</span></div>`).join('');
  return `<div class="lbl" style="margin-top:20px;letter-spacing:.13em">Replacements worth the transfer</div>
    <div class="tbl" style="margin-top:9px">
      <div class="th" style="grid-template-columns:1.4fr .8fr .8fr .9fr"><span>Player</span><span>Price</span><span class="r">Cost</span><span class="r">Form +</span></div>
      ${rows}</div>`;
}

function closeDrawer() { $('#drawer').classList.remove('open'); $('#scrim').hidden = true; }
$('#scrim').addEventListener('click', closeDrawer);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
