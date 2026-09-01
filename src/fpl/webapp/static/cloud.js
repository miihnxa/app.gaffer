/* Hosted-only: account strip, sign-in, and the upgrade path.
   Loaded after app.js, which owns the views. */
(function(){
  let ME = {signed_in:false, pro:false, plan:'anon'};

  const acct = document.getElementById('acct');
  const toast = m => {
    const t = document.createElement('div'); t.className='toast'; t.textContent=m;
    document.body.append(t); setTimeout(()=>t.remove(), 5200);
  };

  async function post(path, body){
    const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
                                body: JSON.stringify(body||{})});
    const j = await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
    return j;
  }

  async function refresh(){
    try{ ME = await (await fetch('/api/me')).json(); }catch(e){}
    paint();
  }

  function paint(){
    if(!acct) return;
    if(!ME.signed_in){
      acct.innerHTML = `<div class="plan">Not signed in</div>
        <input id="em" type="email" placeholder="you@email.com" autocomplete="email">
        <button class="go" id="sendlink">Email me a link</button>`;
      document.getElementById('sendlink').addEventListener('click', async ()=>{
        const email = document.getElementById('em').value.trim();
        if(!email.includes('@')) return toast('Enter a valid email address.');
        try{ const r = await post('/api/auth/request', {email}); toast(r.message); }
        catch(e){ toast(e.message); }
      });
      return;
    }
    acct.innerHTML = `<div class="em">${ME.email}</div>
      <div class="plan">Plan <b>${ME.pro ? 'Pro' : 'Free'}</b></div>
      ${ME.pro ? '<button id="portal">Manage billing</button>'
               : '<button class="go" id="upgrade">Upgrade to Pro</button>'}
      <button id="signout">Sign out</button>`;
    const up = document.getElementById('upgrade');
    if(up) up.addEventListener('click', ()=>startCheckout('monthly'));
    const pt = document.getElementById('portal');
    if(pt) pt.addEventListener('click', async ()=>{
      try{ const r = await post('/api/billing/portal'); location.href = r.url; }
      catch(e){ toast(e.message); }
    });
    document.getElementById('signout').addEventListener('click', async ()=>{
      await post('/api/auth/logout'); location.reload();
    });
  }

  async function startCheckout(cadence){
    if(!ME.signed_in) return toast('Sign in first — we need an email to attach the subscription to.');
    try{ const r = await post('/api/billing/checkout', {cadence}); location.href = r.url; }
    catch(e){ toast(e.message); }
  }

  /* Turn a 402 from any view into an explanation, not a dead end. */
  const origFetch = window.fetch;
  window.fetch = async function(...args){
    const res = await origFetch.apply(this, args);
    if(res.status === 402){
      const clone = res.clone();
      clone.json().then(j=>{
        showLock(j.error || 'This is a Pro feature.');
      }).catch(()=>{});
    }
    return res;
  };

  function showLock(msg){
    const host = document.querySelector('.view:not([hidden])');
    if(!host) return toast(msg);
    const d = document.createElement('div');
    d.className = 'card';
    d.innerHTML = `<div class="lock">
      <h2>Pro feature</h2><p>${msg}</p>
      <div class="row">
        <button class="lockbtn" id="lk-m">Start 7 days free — £3.99/mo</button>
        <button class="lockbtn alt" id="lk-a">£29/year</button>
      </div>
      <p style="font-size:12px;color:var(--ink-3)">Cancel anytime. The free tier keeps working either way.</p>
    </div>`;
    host.textContent=''; host.append(d);
    document.getElementById('lk-m').addEventListener('click', ()=>startCheckout('monthly'));
    document.getElementById('lk-a').addEventListener('click', ()=>startCheckout('annual'));
  }

  const q = new URLSearchParams(location.search);
  if(q.get('checkout') === 'success') toast('You’re on Pro. Everything is unlocked.');
  if(q.get('upgrade')) setTimeout(()=>startCheckout('monthly'), 700);

  refresh();
})();
