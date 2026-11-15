class FamilyChoresPanel extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});this._tab='calendar';this._busy=false;this._lastUser='';}
  set hass(hass){
    this._hass=hass;
    const uid=hass.user?.id||'';
    if(!this._loaded || this._lastUser!==uid){this._lastUser=uid;this._loaded=true;this.load();}
  }
  set panel(p){this._panel=p;}
  set narrow(v){this._narrow=v;}
  esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  async call(type,other={}){return this._hass.connection.sendMessagePromise({type:'family_chores/'+type,...other});}
  async load(){try{this._data=await this.call('snapshot');this._error='';}catch(e){this._error=String(e.message||e);}this.render();}
  async operate(action,data={}){
    if(this._busy)return;
    this._busy=true;
    try{await this.call('manage',{action,data});await this.load();}catch(e){alert(e.message||e);}finally{this._busy=false;}
  }
  async finish(id){try{await this.call('complete',{assignment_id:id});await this.load();}catch(e){alert(e.message||e);}}
  async remove(kind,id,name,impact){
    const future=Number(impact?.future||0),today=Number(impact?.today||0),retained=Number(impact?.retained||0);
    const requested=prompt(`Eliminazione definitiva: ${name}\n\nTurni futuri da annullare: ${future}\nTurni di oggi da annullare: ${today}\nOccorrenze storiche conservate: ${retained}\n\nScrivi esattamente il nome per confermare:`);
    if(requested===null)return;
    if(requested!==name){alert('Nome di conferma non corrispondente. Nessuna modifica effettuata.');return;}
    await this.operate(kind,{id,confirm_name:requested});
  }
  submit(form,action){const values=Object.fromEntries(new FormData(form).entries());if(values.active!==undefined)values.active=values.active==='true';this.operate(action,values);}
  render(){
    const d=this._data;
    const style=`<style>:host{display:block;background:var(--primary-background-color);color:var(--primary-text-color);min-height:100vh;font-family:Roboto,Arial,sans-serif} .wrap{max-width:1050px;margin:auto;padding:20px}header{display:flex;align-items:center;gap:12px}h1{font-size:24px;margin:0 0 10px}h2{font-size:19px;margin:18px 0 10px}nav{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}button{border:0;cursor:pointer;border-radius:8px;padding:10px 13px;background:var(--primary-color,#168bd2);color:white}button:disabled{opacity:.45;cursor:default}nav button{background:var(--secondary-background-color,#ddd);color:var(--primary-text-color)}nav button.selected{background:var(--primary-color,#168bd2);color:white} .card{border:1px solid var(--divider-color,#ddd);border-radius:12px;padding:13px;margin:9px 0;background:var(--card-background-color)}.flex{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.muted{opacity:.72;font-size:13px}.red{border-left:6px solid #cc3535}.yellow{border-left:6px solid #e6b72d}.green{border-left:6px solid #31995e}.missed{color:#b52e2e}label{display:block;margin:9px 0}input,select{font:inherit;box-sizing:border-box;max-width:100%;padding:9px;margin:3px 0;border:1px solid var(--divider-color,#bbb);border-radius:6px;background:var(--card-background-color);color:var(--primary-text-color)}input[type=checkbox]{height:23px;width:23px;accent-color:var(--primary-color,#168bd2)}form{display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin:14px 0}form label{margin:0}form button{height:40px}.line{border-bottom:1px solid var(--divider-color,#ddd);padding:10px 0}.alert{background:rgba(204,53,53,.07);border-left:5px solid #c33}.danger{background:#aa3030}.pill{border-radius:20px;padding:3px 8px;background:var(--secondary-background-color,#eee);font-size:12px}summary{cursor:pointer;padding:8px 0}</style>`;
    if(!d){this.shadowRoot.innerHTML=style+`<div class="wrap"><h1>Faccende di casa</h1><div>${this.esc(this._error||'Caricamento…')}</div><button id="reload">Riprova</button></div>`;this.shadowRoot.getElementById('reload').onclick=()=>this.load();return;}
    if(!d.admin && this._tab!=='calendar')this._tab='calendar';
    const tabs=[['calendar','Calendario'],...(d.admin?[['users','Utenti'],['chores','Faccende'],['alerts','Anomalie ('+d.alerts.length+')'],['history','Storico']]:[])];
    let html=style+`<div class="wrap"><header><button id="menu" title="Menu Home Assistant">☰</button><div><h1>Faccende di casa</h1><div class="muted">${this.esc(d.today)} · ${d.admin?'Amministratore':'Ospite'}</div></div></header><nav>${tabs.map(([k,t])=>`<button data-tab="${k}" class="${this._tab===k?'selected':''}">${this.esc(t)}</button>`).join('')}</nav>`;
    if(this._tab==='calendar'){
      html+='<h2>Prossime faccende</h2>';
      if(!d.schedule.length) html+='<p>Nessuna faccenda pianificata.</p>';
      for(const a of d.schedule){
        const diff=Math.round((Date.parse(a.due_date+'T12:00:00')-Date.parse(d.today+'T12:00:00'))/86400000);
        const color=diff===0?'red':diff===1?'yellow':'green';
        const label=diff===0?'Oggi':diff===1?'Domani':`Tra ${diff} giorni`;
        const can=a.mine&&a.status==='pending';
        html+=`<div class="card ${color} flex"><div><strong>${this.esc(a.chore)}</strong><div class="muted">${this.esc(label)} · ${this.esc(a.due_date)} · ${this.esc(a.assignee||'Non assegnata')}${a.mine?' · È tua':''}</div></div><div>${a.status==='completed'?'✓ Completata':can?`<label><input type="checkbox" data-complete="${a.id}" aria-label="Completa ${this.esc(a.chore)}"> Fatto</label>`:a.mine?'🔒':a.assignee?'':'⚠️ Nessun assegnatario'}</div></div>`;
      }
    }else if(this._tab==='users'){
      const free=d.available_ha_users||[];
      const choices=free.map(u=>`<option value="${this.esc(u.id)}">${this.esc(u.name)}</option>`).join('');
      html+=`<h2>Utenti</h2><p class="muted">Seleziona un account Home Assistant disponibile: l'ID viene associato automaticamente. Gli account già utilizzati (anche da ospiti sospesi) non compaiono.</p><form data-form="add_user"><label>Nome ospite<input name="name" required></label><label>Account Home Assistant<select name="ha_user_id" required ${free.length?'':'disabled'}><option value="">Seleziona un account…</option>${choices}</select></label><button ${free.length?'':'disabled'}>Aggiungi</button></form>`;
      if(!free.length)html+='<p class="muted">Nessun account Home Assistant libero e attivo disponibile.</p>';
      for(const u of d.users){
        // The current account is allowed when editing its own association.
        const current=`<option value="${this.esc(u.ha_user_id)}" selected>${this.esc(u.ha_display_name||u.name)} (attuale)</option>`;
        html+=`<details class="card"><summary>${this.esc(u.name)} · ${u.active?'Attivo':'Sospeso'}</summary><form data-form="edit_user"><input type="hidden" name="id" value="${u.id}"><label>Nome<input name="name" value="${this.esc(u.name)}" required></label><label>Account Home Assistant<select name="ha_user_id" required>${current}${choices}</select></label><label>Stato<select name="active"><option value="true" ${u.active?'selected':''}>Attivo</option><option value="false" ${!u.active?'selected':''}>Sospeso</option></select></label><button>Salva</button></form><form data-form="absence"><input type="hidden" name="user_id" value="${u.id}"><label>Assente dal<input type="date" name="start_date" required></label><label>Al<input type="date" name="end_date" required></label><button>Registra assenza</button></form><button class="danger" data-delete-user="${u.id}">Elimina definitivamente</button></details>`;
      }
      if(d.absences.length)html+='<h2>Periodi di assenza</h2>'+d.absences.map(a=>`<div class="line">${this.esc(a.user_name)}: ${a.start_date} → ${a.end_date}</div>`).join('');
    }else if(this._tab==='chores'){
      html+=`<h2>Faccende</h2><form data-form="add_chore"><label>Nome<input name="name" required></label><label>Data iniziale<input type="date" name="start_date" required></label><label>Ogni quanti giorni<input type="number" name="frequency" min="1" value="1" required></label><button>Aggiungi</button></form>`;
      for(const c of d.chores)html+=`<div class="card"><div class="flex"><strong>${this.esc(c.name)}</strong><span class="pill">${c.active?'Attiva':'Archiviata'} · ogni ${c.frequency} gg · dal ${c.start_date}</span></div><form data-form="edit_chore"><input name="id" type="hidden" value="${c.id}"><label>Nome<input name="name" required value="${this.esc(c.name)}"></label><label>Stato<select name="active"><option value="true" ${c.active?'selected':''}>Attiva</option><option value="false" ${!c.active?'selected':''}>Archiviata</option></select></label><button>Salva</button></form><button class="danger" data-delete-chore="${c.id}">Elimina definitivamente</button></div>`;
      html+='<p class="muted">La prima versione mantiene immutabili data iniziale e frequenza di una faccenda esistente: per cambiarle, archiviarla e crearne una nuova. Lo storico resta conservato.</p>';
    }else if(this._tab==='alerts'){
      html+='<h2>Faccende non completate</h2>';
      if(!d.alerts.length)html+='<p>Nessuna anomalia da visionare.</p>';
      for(const a of d.alerts)html+=`<div class="card alert flex"><div><strong>${this.esc(a.chore)}</strong><div class="muted">${this.esc(a.assignee||'Non assegnata')} · ${this.esc(a.due_date)}</div></div><button data-ack="${a.id}">Presa visione</button></div>`;
    }else if(this._tab==='history'){
      html+='<h2>Storico (ultime 300)</h2>';
      for(const a of d.history)html+=`<div class="line flex"><div><strong>${this.esc(a.chore)}</strong><div class="muted">${a.due_date} · ${this.esc(a.assignee||'Non assegnata')}</div></div><span class="${a.status==='missed'?'missed':''}">${a.status==='missed'?'Non completata':a.status==='cancelled'?'Annullata':'Completata'}</span></div>`;
    }
    html+='</div>';this.shadowRoot.innerHTML=html;
    this.shadowRoot.getElementById('menu').onclick=()=>this.dispatchEvent(new Event('hass-toggle-menu',{bubbles:true,composed:true}));
    this.shadowRoot.querySelectorAll('[data-tab]').forEach(e=>e.onclick=()=>{this._tab=e.dataset.tab;this.render();});
    this.shadowRoot.querySelectorAll('[data-complete]').forEach(e=>e.onchange=()=>this.finish(Number(e.dataset.complete)));
    this.shadowRoot.querySelectorAll('[data-ack]').forEach(e=>e.onclick=()=>this.operate('acknowledge',{id:Number(e.dataset.ack)}));
    this.shadowRoot.querySelectorAll('[data-delete-user]').forEach(e=>e.onclick=()=>{const u=d.users.find(u=>u.id===Number(e.dataset.deleteUser));if(u)this.remove('delete_user',u.id,u.name,u.deletion_impact);});
    this.shadowRoot.querySelectorAll('[data-delete-chore]').forEach(e=>e.onclick=()=>{const c=d.chores.find(c=>c.id===Number(e.dataset.deleteChore));if(c)this.remove('delete_chore',c.id,c.name,c.deletion_impact);});
    this.shadowRoot.querySelectorAll('[data-form]').forEach(e=>e.onsubmit=ev=>{ev.preventDefault();this.submit(e,e.dataset.form);});
  }
}
if(!customElements.get('family-chores-panel')){customElements.define('family-chores-panel',FamilyChoresPanel);}
