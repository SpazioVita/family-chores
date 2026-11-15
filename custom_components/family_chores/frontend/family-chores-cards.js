/* Family Chores v0.5: two Home Assistant Lovelace cards.
   - family-chores-my-card: personal assignments + authorized completion
   - family-chores-board-card: kiosk, read-only today and tomorrow
*/
const FC_STYLE = `<style>
:host{display:block;color:var(--primary-text-color);font:inherit}
ha-card{display:block;overflow:hidden}
.head{display:flex;align-items:center;justify-content:space-between;padding:18px 18px 8px;gap:10px}
.title{font-size:19px;font-weight:600}.sub{font-size:12px;opacity:.7;margin-top:4px}
.section{padding:10px 18px 6px;font-size:14px;font-weight:600}
.item{padding:12px 14px;margin:9px 14px;border:1px solid var(--divider-color,#ddd);border-left:5px solid #32945a;border-radius:9px;display:flex;justify-content:space-between;gap:12px;align-items:center}
.item.today{border-left-color:#ca3c36}.item.tomorrow{border-left-color:#d5ab2a}
.name{font-weight:600;overflow-wrap:anywhere}.meta{font-size:12px;opacity:.75;margin-top:5px}
.actions{flex-shrink:0;white-space:nowrap;font-size:12px}.actions label{display:flex;align-items:center;gap:7px;cursor:pointer}.actions input{width:23px;height:23px;accent-color:var(--primary-color,#1675ac)}
.empty,.error{padding:16px 18px;font-size:14px}.error{color:var(--error-color,#ca3030)}
.small{font-size:12px;opacity:.7;padding:0 18px 14px}
</style>`;
class FamilyChoresCardBase extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});this._loading=false;this._started=false;this._data=null;this._error='';this._busy=false;this._unsub=null;}
  setConfig(config){this._config=config||{};this.render();}
  getCardSize(){return 4;}
  connectedCallback(){this._active=true;this._start();}
  disconnectedCallback(){this._active=false;clearTimeout(this._midnight);clearInterval(this._poll);if(this._unsub){this._unsub();this._unsub=null;}this._started=false;}
  set hass(hass){
    const id=hass?.user?.id, conn=hass?.connection;
    const changed=this._userId!==id||this._conn!==conn;
    this._hass=hass;this._userId=id;this._conn=conn;
    if(changed){this._data=null;this._error='';this._started=false;clearTimeout(this._midnight);clearInterval(this._poll);if(this._unsub){this._unsub();this._unsub=null;}}
    this._start();
  }
  esc(v){return String(v??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));}
  _start(){
    if(!this._active||!this._hass?.connection||this._started)return;
    this._started=true;
    this.reload();
    // Event-triggered updates plus a 60-second safety sync for reconnects/clock drift.
    this._hass.connection.subscribeEvents(()=>this.reload(),'family_chores_updated')
      .then(unsub=>{if(this._active)this._unsub=unsub;else unsub();})
      .catch(()=>{});
    this._poll=setInterval(()=>{if(this._active)this.reload();},60000);
  }
  async reload(){
    if(this._loading||!this._hass?.connection)return;
    this._loading=true;
    try{
      const type=this._type==='board'?'family_chores/board':'family_chores/snapshot';
      const result=await this._hass.connection.sendMessagePromise({type});
      if(!this._active)return;
      this._data=result;this._error='';
      clearTimeout(this._midnight);
      const seconds=Number(result.seconds_to_midnight);
      // Backend computes the local HA midnight; small delay lets maintenance close the day.
      const delay=Number.isFinite(seconds)?Math.max(200,Math.min(2147483647,seconds*1000+2500)):60000;
      this._midnight=setTimeout(()=>this.reload(),delay);
    }catch(e){this._error=String(e.message||e);}
    finally{this._loading=false;if(this._active)this.render();}
  }
  status(a){return a.status==='completed'?'Completata':a.status==='missed'?'Non completata':a.status==='pending'?'Da fare':'Programmata';}
  render(){
    if(!this.shadowRoot)return;
    const d=this._data, title=this._type==='board'?'Faccende comuni':'Le mie faccende';
    let html=FC_STYLE+`<ha-card><div class="head"><div><div class="title">${this.esc(this._config?.title||title)}</div><div class="sub">${this._type==='board'?'Oggi e domani · sola lettura':'Assegnazioni personali · prossimi 14 giorni'}</div></div><span>🧹</span></div>`;
    if(this._error)html+=`<div class="error">${this.esc(this._error)}</div>`;
    if(!d){html+=`<div class="empty">Caricamento…</div></ha-card>`;this.shadowRoot.innerHTML=html;return;}
    let items=d.schedule||[];
    if(this._type==='my')items=items.filter(a=>a.mine);
    if(!items.length){html+=`<div class="empty">${this._type==='board'?'Nessuna faccenda prevista oggi o domani.':'Nessuna faccenda assegnata nei prossimi 14 giorni.'}</div>`;}
    const today=d.today;
    const tomorrowDate=new Date(today+'T12:00:00');tomorrowDate.setDate(tomorrowDate.getDate()+1);
    const tomorrow=`${tomorrowDate.getFullYear()}-${String(tomorrowDate.getMonth()+1).padStart(2,'0')}-${String(tomorrowDate.getDate()).padStart(2,'0')}`;
    let lastDay='';
    for(const a of items){
      if(this._type==='board'&&a.due_date!==today&&a.due_date!==tomorrow)continue;
      let label=a.due_date===today?'Oggi':a.due_date===tomorrow?'Domani':a.due_date;
      if(this._type==='board'&&lastDay!==label){html+=`<div class="section">${this.esc(label)}</div>`;lastDay=label;}
      const dayClass=a.due_date===today?'today':a.due_date===tomorrow?'tomorrow':'';
      const canComplete=this._type==='my'&&a.mine&&a.due_date===today&&a.status==='pending';
      const completion=this._type==='my' ? `<div class="actions">${a.status==='completed'?'✓ Fatto':canComplete?`<label><input type="checkbox" data-complete="${Number(a.id)}" ${this._busy?'disabled':''}> Fatto</label>`:'🔒'}</div>` : '';
      html+=`<div class="item ${dayClass}"><div><div class="name">${this.esc(a.chore)}</div><div class="meta">${this._type==='board'?this.esc(a.assignee||'Non assegnata')+' · ':''}${this.esc(label)} · ${this.esc(this.status(a))}</div></div>${completion}</div>`;
    }
    if(this._type==='board')html+='<div class="small">La bacheca non permette di confermare le faccende.</div>';
    html+='</ha-card>';this.shadowRoot.innerHTML=html;
    if(this._type==='my')this.shadowRoot.querySelectorAll('[data-complete]').forEach(node=>node.addEventListener('change',async()=>{
      if(this._busy||!node.checked)return;this._busy=true;node.disabled=true;
      try{await this._hass.connection.sendMessagePromise({type:'family_chores/complete',assignment_id:Number(node.dataset.complete)});await this.reload();}
      catch(e){window.alert(String(e.message||e));node.checked=false;}
      finally{this._busy=false;this.render();}
    }));
  }
}
class FamilyChoresMyCard extends FamilyChoresCardBase{constructor(){super();this._type='my';}}
class FamilyChoresBoardCard extends FamilyChoresCardBase{constructor(){super();this._type='board';}}
if(!customElements.get('family-chores-my-card'))customElements.define('family-chores-my-card',FamilyChoresMyCard);
if(!customElements.get('family-chores-board-card'))customElements.define('family-chores-board-card',FamilyChoresBoardCard);
window.customCards=window.customCards||[];
for(const card of [{type:'family-chores-my-card',name:'Family Chores - Personale',description:'Faccende assegnate all’utente corrente'},{type:'family-chores-board-card',name:'Family Chores - Bacheca',description:'Oggi e domani, per tutti, senza comandi'}]){
  if(!window.customCards.some(x=>x.type===card.type))window.customCards.push(card);
}
