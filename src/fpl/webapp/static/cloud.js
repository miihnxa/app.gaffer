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
      <div class="plan">Team saved to your account</div>
      <button id="signout">Sign out</button>`;
    document.getElementById('signout').addEventListener('click', async ()=>{
      await post('/api/auth/logout'); location.reload();
    });
  }

  refresh();
})();
