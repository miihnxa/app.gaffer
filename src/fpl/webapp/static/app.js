/* Gaffer — local FPL assistant. Read-only: nothing here ever changes a team. */
const $  = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
const el = (t,c,h) => { const n=document.createElement(t); if(c)n.className=c; if(h!==undefined)n.innerHTML=h; return n; };
const money = v => '£'+Number(v).toFixed(1)+'m';
const nfmt  = v => v==null ? '—' : Number(v).toLocaleString();
const fdrTag = d => `<span class="fdr fdr${d}">${d}</span>`;
const fxText = p => p.fixtures_gw.length
  ? p.fixtures_gw.map(f=>`${f.opponent} ${f.home?'H':'A'} ${fdrTag(f.difficulty)}`).join(' ')
  : '<span style="color:var(--crit)">BLANK</span>';

const S = { team:null, teamId:null, season:null, view:'squad', league:null, rebuild:null,
            locks:new Set(), bench:19.0 };

async function api(path){
  const r = await fetch(path);
  const body = await r.json().catch(()=>({error:`HTTP ${r.status}`}));
  if(!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
  return body;
}
function busy(on, msg){ $('#loading').hidden = !on; if(msg) $('#loadmsg').textContent = msg; }
function fail(msg){ const e=$('#err'); e.hidden=!msg; e.textContent=msg||''; }

/* ---------------- boot ---------------- */
(async function init(){
  try{
    const [season, cfg] = await Promise.all([api('/api/season'), api('/api/config')]);
    S.season = season;
    $('#railgw').textContent = `GW${season.next_gw} · ${season.deadline_local}`;
    $('#railcd').textContent = season.countdown + ' to go';
    renderRecents(cfg.recents);
    if(cfg.default_team_id){ $('#tid').value = cfg.default_team_id; loadTeam(cfg.default_team_id); }
    else { $('#v-squad').append(hero()); $('#teammenu').hidden = false; }
  }catch(e){ fail('Could not reach the FPL API. Check your connection, then reopen. ('+e.message+')'); }
})();

function hero(){
  const d = el('div','hero');
  d.innerHTML = `<h2>Load a team</h2>
    <p>Enter any FPL team ID to see its squad, fixtures, flagged players and the
       transfers that actually improve it. Works for any manager in the game — it reads
       the public Fantasy Premier League data and never signs in.</p>`;
  return d;
}
function renderRecents(rows){
  const box = $('#recents'); box.textContent='';
  if(!rows || !rows.length) return;
  box.append(el('div','mlabel','Recent'));
  rows.forEach(r=>{
    const b = el('button','rec',`<b>${r.name}</b><br><span style="font-size:11.5px">${r.manager} · ${r.id}</span>`);
    b.type='button';
    b.addEventListener('click',()=>{ $('#tid').value=r.id; loadTeam(r.id); });
    box.append(b);
  });
}

/* ---------------- team ---------------- */
async function loadTeam(id){
  fail(''); busy(true,'Loading team…'); $('#teammenu').hidden = true;
  try{
    S.teamId = Number(id);
    S.team = await api('/api/team/'+id);
    S.locks = new Set(); S.rebuild = null; S.league = null;
    paintHeader();
    render();
  }catch(e){ fail(e.message); }
  finally{ busy(false); }
}
function paintHeader(){
  const e = S.team.entry;
  $('#teamname').textContent = e.name;
  $('#teammeta').textContent = `${e.manager}${e.region ? ' · '+e.region : ''} · ID ${e.id}`;
  $('#tstats').textContent='';
  [['Overall', nfmt(e.overall_points)+' pts'],
   ['World rank', nfmt(e.overall_rank)],
   ['Squad value', money(S.team.squad.value)],
   ['Bank', money(S.team.squad.bank)],
   ['To act on', String(S.team.advice.length)]
  ].forEach(([k,v])=>{
    const d=el('div','st'); d.append(el('div','v',v), el('div','k',k)); $('#tstats').append(d);
  });
}

/* ---------------- nav ---------------- */
$$('#nav .nv').forEach(b=>b.addEventListener('click',()=>{
  S.view = b.dataset.view;
  $$('#nav .nv').forEach(x=>x.setAttribute('aria-pressed', String(x===b)));
  render();
}));
function render(){
  ['squad','rebuild','league','players'].forEach(v=>{ $('#v-'+v).hidden = v!==S.view; });
  if(!S.team && S.view!=='players'){ return; }
  if(S.view==='squad')   renderSquad();
  if(S.view==='rebuild') renderRebuild();
  if(S.view==='league')  renderLeague();
  if(S.view==='players') renderPlayers();
}

/* ---------------- squad ---------------- */
function chip(p, opts={}){
  const cls = p.status==='ok' ? '' : (p.severity==='critical'?'f-crit':'f-warn');
  const b = el('button','pl '+cls);
  b.type='button'; b.dataset.id = p.id;
  b.innerHTML = `<div class="bar"></div>
    <div class="nm">${p.name}</div>
    <div class="fx">${fxText(p)}</div>
    <div class="mt"><span>${money(p.price)}</span><span><b>${p.form}</b></span></div>
    ${p.is_captain?'<span class="badge c">C</span>':p.is_vice?'<span class="badge v">V</span>':''}
    ${p.status!=='ok'?'<span class="badge flag">!</span>':''}
    ${opts.lock&&p.locked?'<span class="badge lock">🔒</span>':''}`;
  b.addEventListener('click',()=>openPlayer(p));
  return b;
}
function pitchEl(xi, bench, opts={}){
  const p = el('div','pitch');
  ['GKP','DEF','MID','FWD'].forEach(pos=>{
    const line = xi.filter(x=>x.pos===pos);
    if(!line.length) return;
    const r = el('div','row'); line.forEach(x=>r.append(chip(x,opts))); p.append(r);
  });
  const b = el('div','benchstrip'); b.append(el('span','lbl','Bench'));
  bench.forEach(x=>b.append(chip(x,opts))); p.append(b);
  return p;
}
function renderSquad(){
  const v = $('#v-squad'); v.textContent='';
  const sq = S.team.squad;
  const wrap = el('div','grid2');

  const left = el('div','stack');
  const pc = el('div','card');
  pc.append(hd(`GW${S.season.next_gw} squad`, sq.formation));
  const body = el('div','bd');
  if(sq.stale || sq.source!=='api') body.append(el('p','note', sq.note));
  body.append(pitchEl(sq.xi, sq.bench));
  body.append(el('p','', `<span style="font-size:11.5px;color:var(--ink-3)">Click a player for form, fixtures and the transfers that clear the rules.</span>`));
  pc.append(body); left.append(pc);

  const tc = el('div','card'); tc.append(hd('Full squad', `${money(sq.value)} · ${money(sq.bank)} bank`));
  const tw = el('div','tw'); tw.append(squadTable(sq)); tc.append(tw); left.append(tc);

  const right = el('div','stack');
  const ac = el('div','card');
  ac.append(hd('What to look at', S.team.advice.length ? S.team.advice.length+' item'+(S.team.advice.length>1?'s':'') : 'all clear'));
  if(!S.team.advice.length){
    ac.append(el('div','empty','Nothing to change. The squad is legal, nobody in the XI is flagged, and the bench order is sound.'));
  } else {
    S.team.advice.forEach(a=>{
      const d = el('div','adv-item '+a.severity);
      d.append(el('div','stripe'));
      d.append(el('div','',`<span class="pill">${a.severity}</span><h3>${a.title}</h3><p>${a.detail}</p>`));
      ac.append(d);
    });
  }
  right.append(ac);

  const lc = el('div','card'); lc.append(hd('Leagues',''));
  const lb = el('div','bd'); lb.style.padding='0';
  const t = el('table'); t.innerHTML = '<thead><tr><th>League</th><th class="n">Rank</th></tr></thead>';
  const tb = el('tbody');
  S.team.leagues.forEach(l=>{
    const tr = el('tr');
    tr.innerHTML = `<td>${l.name}</td><td class="n">${nfmt(l.rank)}</td>`;
    tr.style.cursor='pointer';
    tr.addEventListener('click',()=>{ S.view='league'; S.leagueId=l.id;
      $$('#nav .nv').forEach(x=>x.setAttribute('aria-pressed', String(x.dataset.view==='league'))); render(); });
    tb.append(tr);
  });
  t.append(tb); lb.append(t); lc.append(lb); right.append(lc);

  wrap.append(left,right); v.append(wrap);
}
function hd(title, right){
  const h = el('div','hd'); h.append(el('h2','',title));
  if(right!==undefined) h.append(el('span','eyebrow',right));
  return h;
}
function squadTable(sq){
  const t = el('table');
  t.innerHTML = `<thead><tr><th>Player</th><th>Club</th><th>Pos</th><th class="n">Price</th>
    <th class="n">Form</th><th class="n">Pts</th><th class="n">Sel%</th><th>Next</th><th class="n">5GW</th><th>Status</th></tr></thead>`;
  const tb = el('tbody');
  sq.xi.concat(sq.bench).forEach(p=>{
    const tr = el('tr', p.benched?'benched':'');
    const badge = p.is_captain?' (C)':p.is_vice?' (V)':'';
    tr.innerHTML = `<td><b>${p.name}</b>${badge}</td><td>${p.club}</td><td>${p.pos}</td>
      <td class="n">${money(p.price)}</td><td class="n">${p.form}</td><td class="n">${p.points}</td>
      <td class="n">${p.selected}%</td><td>${fxText(p)}</td><td class="n">${p.fdr5}</td>
      <td style="color:${p.status==='ok'?'var(--ink-3)':'var(--crit)'}">${p.status==='ok'?'—':p.status}</td>`;
    tr.style.cursor='pointer';
    tr.addEventListener('click',()=>openPlayer(p));
    tb.append(tr);
  });
  t.append(tb); return t;
}

/* ---------------- rebuild ---------------- */
function renderRebuild(){
  const v = $('#v-rebuild'); v.textContent='';
  const card = el('div','card');
  card.append(hd('Rebuild the squad', `budget ${money(S.team.squad.value + S.team.squad.bank)}`));

  const c = el('div','ctrls');
  c.innerHTML = `<div class="ctrl"><label for="bslide">Bench budget</label>
      <input id="bslide" type="range" min="16" max="30" step="0.5" value="${S.bench}">
      <output id="bout">${money(S.bench)}</output></div>
    <button id="rgo" class="btn primary sm">Build squad</button>
    <span style="font-size:12px;color:var(--ink-3)">Buys the bench first, so a Bench Boost is worth playing.</span>`;
  card.append(c);

  const locks = el('div','locks');
  locks.append(el('span','eyebrow','Keep — click to lock'));
  S.team.squad.xi.concat(S.team.squad.bench).forEach(p=>{
    const b = el('button','lockchip',`${p.name} ${money(p.price)}`);
    b.type='button'; b.setAttribute('aria-pressed', String(S.locks.has(p.id)));
    b.addEventListener('click',()=>{
      S.locks.has(p.id) ? S.locks.delete(p.id) : S.locks.add(p.id);
      b.setAttribute('aria-pressed', String(S.locks.has(p.id)));
    });
    locks.append(b);
  });
  card.append(locks);

  const out = el('div','bd'); out.id='rout';
  if(S.rebuild) out.append(rebuildResult(S.rebuild));
  else out.append(el('p','',`<span style="color:var(--ink-3);font-size:13px">Lock the players you want to keep, set a bench budget, then build. Nothing is applied — it's a plan you type in yourself.</span>`));
  card.append(out); v.append(card);

  $('#bslide').addEventListener('input', e=>{ S.bench = Number(e.target.value); $('#bout').textContent = money(S.bench); });
  $('#rgo').addEventListener('click', doRebuild);
}
async function doRebuild(){
  fail(''); busy(true,'Building a legal 15…');
  try{
    const q = new URLSearchParams(); q.set('bench', S.bench);
    S.locks.forEach(id=>q.append('lock', id));
    S.rebuild = await api(`/api/team/${S.teamId}/rebuild?${q}`);
    const out = $('#rout'); out.textContent=''; out.append(rebuildResult(S.rebuild));
  }catch(e){ fail(e.message); }
  finally{ busy(false); }
}
function rebuildResult(r){
  const box = el('div','stack');
  box.append(el('p','',`<span style="font-size:13px;color:var(--ink-2)">
    <b style="color:var(--ink)">${r.formation}</b> · ${money(r.cost)} spent, ${money(r.spare)} spare ·
    Bench Boost ready <b style="color:${r.bench_ready===4?'var(--accent)':'var(--warn)'}">${r.bench_ready}/4</b></span>`));
  box.append(pitchEl(r.xi, r.bench, {lock:true}));

  const t = el('table');
  t.innerHTML = '<thead><tr><th>Bench</th><th class="n">Minutes</th><th>Next</th><th>Verdict</th></tr></thead>';
  const tb = el('tbody');
  r.bench_detail.forEach(b=>{
    tb.append(el('tr','',`<td><b>${b.name}</b> <span style="color:var(--ink-3)">${b.club}</span></td>
      <td class="n">${b.minutes}′ (${Math.round(b.share*100)}%)</td>
      <td>${b.fixture} ${fdrTag(b.fdr)}</td>
      <td class="${b.ok?'up':'dn'}">${b.verdict}</td>`));
  });
  t.append(tb);
  const tw = el('div','tw'); tw.append(t); box.append(tw);

  box.append(el('p','',`<span style="font-size:12.5px;color:var(--ink-2)">
    <b style="color:var(--ink)">Keeps</b> ${r.kept.join(', ')||'none'}<br>
    <b style="color:var(--ink)">Sells</b> ${r.out.join(', ')||'none'}</span>`));
  return box;
}

/* ---------------- league ---------------- */
async function renderLeague(){
  const v = $('#v-league'); v.textContent='';
  const id = S.leagueId || (S.team.leagues.find(l=>l.rank && l.size && l.size<200)||S.team.leagues[0]||{}).id;
  if(!id){ v.append(el('div','empty','No leagues found for this team.')); return; }
  busy(true,'Loading standings…');
  try{
    S.league = await api(`/api/league/${id}?team=${S.teamId}`);
    const card = el('div','card');
    card.append(hd(S.league.name, `${S.league.rows.length} teams`));
    const t = el('table');
    t.innerHTML = `<thead><tr><th class="n">#</th><th>Team</th><th>Manager</th>
      <th class="n">GW</th><th class="n">Total</th><th class="n">Move</th></tr></thead>`;
    const tb = el('tbody');
    S.league.rows.forEach(r=>{
      const tr = el('tr', r.is_me?'me':'');
      const mv = r.moved>0?`<span class="up">▲${r.moved}</span>`:r.moved<0?`<span class="dn">▼${-r.moved}</span>`:'—';
      tr.innerHTML = `<td class="n">${r.rank}</td><td><b>${r.name}</b></td><td>${r.manager}</td>
        <td class="n">${r.gw}</td><td class="n">${r.total}</td><td class="n">${mv}</td>`;
      tr.style.cursor='pointer';
      tr.addEventListener('click',()=>{ $('#tid').value=r.entry; loadTeam(r.entry);
        S.view='squad'; $$('#nav .nv').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.view==='squad'))); });
      tb.append(tr);
    });
    t.append(tb);
    const tw = el('div','tw'); tw.append(t); card.append(tw);
    card.append(el('p','',`<span style="display:block;padding:11px 15px;font-size:12px;color:var(--ink-3)">Click any rival to open their squad.</span>`));
    v.append(card);
  }catch(e){ fail(e.message); }
  finally{ busy(false); }
}

/* ---------------- players ---------------- */
function renderPlayers(){
  const v = $('#v-players');
  if(v.dataset.built) return;
  v.dataset.built = '1';
  const card = el('div','card');
  card.append(hd('Player search',''));
  const bd = el('div','bd');
  bd.innerHTML = `<input class="srch" id="pq" type="search" placeholder="Search any player by name…" autocomplete="off">`;
  card.append(bd);
  const res = el('div','tw'); res.id='pres'; card.append(res);
  v.append(card);
  let timer;
  $('#pq').addEventListener('input', e=>{
    clearTimeout(timer);
    const q = e.target.value;
    timer = setTimeout(async ()=>{
      if(q.trim().length<2){ $('#pres').textContent=''; return; }
      try{
        const rows = await api('/api/search?q='+encodeURIComponent(q));
        const t = el('table');
        t.innerHTML = `<thead><tr><th>Player</th><th>Club</th><th>Pos</th><th class="n">Price</th>
          <th class="n">Form</th><th class="n">Pts</th><th class="n">Sel%</th><th class="n">5GW</th><th>Status</th></tr></thead>`;
        const tb = el('tbody');
        rows.forEach(p=>tb.append(el('tr','',`<td><b>${p.name}</b></td><td>${p.club}</td><td>${p.pos}</td>
          <td class="n">${money(p.price)}</td><td class="n">${p.form}</td><td class="n">${p.points}</td>
          <td class="n">${p.selected}%</td><td class="n">${p.fdr5}</td>
          <td style="color:${p.flagged?'var(--crit)':'var(--ink-3)'}">${p.flagged?p.status:'—'}</td>`)));
        t.append(tb);
        $('#pres').textContent=''; $('#pres').append(t);
      }catch(err){ fail(err.message); }
    }, 220);
  });
}

/* ---------------- drawer ---------------- */
function openPlayer(p){
  $$('.pl').forEach(n=>n.classList.toggle('sel', n.dataset.id==String(p.id)));
  $('#dbody').innerHTML = `
    <div class="eyebrow">${p.club} · ${p.pos}${p.benched?' · bench':''}</div>
    <h2 style="font-size:28px;margin-top:2px">${p.name}</h2>
    <div class="dgrid">
      <div class="b"><div class="k">Price</div><div class="v">${money(p.price)}</div></div>
      <div class="b"><div class="k">Form</div><div class="v">${p.form}</div></div>
      <div class="b"><div class="k">Points</div><div class="v">${p.points}</div></div>
      <div class="b"><div class="k">Per game</div><div class="v">${p.ppg ?? '—'}</div></div>
      <div class="b"><div class="k">Minutes</div><div class="v">${p.minutes ?? '—'}</div></div>
      <div class="b"><div class="k">Selected</div><div class="v">${p.selected}%</div></div>
    </div>
    <div class="eyebrow">Next five</div>
    <div class="fxrow">${p.fixtures_next.map(f=>`<span>GW${f.gw} ${f.opponent} ${f.home?'(H)':'(A)'} ${fdrTag(f.difficulty)}</span>`).join('') || '<span>No scheduled fixtures</span>'}</div>
    ${p.status!=='ok' ? `<div class="news"><b>${p.status}</b>${p.news?' — '+p.news:''} · ${p.chance}% chance to play</div>` : ''}
    ${repsTable(p)}`;
  $('#drawer').classList.add('open'); $('#scrim').hidden = false;
}
function repsTable(p){
  if(!p.replacements || !p.replacements.length){
    return `<div class="eyebrow" style="margin-top:16px">Replacements</div>
      <p style="font-size:12.5px;color:var(--ink-2);margin:6px 0 0">
        Nothing in this position improves on ${p.name} within ${money(p.price)} + ${money(S.team.squad.bank)} bank.
        Every candidate is lower form, flagged, unaffordable, or would break the 3-per-club limit.</p>`;
  }
  const rows = p.replacements.map(r=>`<tr>
    <td><b>${r.name}</b></td><td>${r.club}</td><td class="n">${money(r.price)}</td>
    <td class="n ${r.cost>0?'dn':''}">${r.cost>0?'+':''}${r.cost.toFixed(1)}</td>
    <td class="n up">+${r.form_delta.toFixed(1)}</td><td class="n">${r.form}</td>
    <td>${r.fixture} ${fdrTag(r.fdr)}</td><td class="n">${r.fdr5}</td></tr>`).join('');
  return `<div class="eyebrow" style="margin-top:18px">Replacements worth the transfer</div>
    <div class="tw"><table>
      <thead><tr><th>Player</th><th>Club</th><th class="n">Price</th><th class="n">Cost</th>
        <th class="n">Form +</th><th class="n">Form</th><th>Next</th><th class="n">5GW</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
    <p style="font-size:11.5px;color:var(--ink-3);margin:8px 0 0">
      Higher form than ${p.name}, fit, affordable, and legal on the 3-per-club rule. Ranked by form and fixtures.</p>`;
}
function closeDrawer(){
  $('#drawer').classList.remove('open'); $('#scrim').hidden = true;
  $$('.pl').forEach(n=>n.classList.remove('sel'));
}
$('#dx').addEventListener('click', closeDrawer);
$('#scrim').addEventListener('click', closeDrawer);
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeDrawer(); });

/* ---------------- team menu ---------------- */
$('#teambtn').addEventListener('click', ()=>{ $('#teammenu').hidden = !$('#teammenu').hidden; });
$('#tgo').addEventListener('click', ()=>{ const v=$('#tid').value.trim(); if(v) loadTeam(v); });
$('#tid').addEventListener('keydown', e=>{ if(e.key==='Enter'){ const v=e.target.value.trim(); if(v) loadTeam(v); }});
document.addEventListener('click', e=>{
  if(!$('.teambox').contains(e.target)) $('#teammenu').hidden = true;
});
