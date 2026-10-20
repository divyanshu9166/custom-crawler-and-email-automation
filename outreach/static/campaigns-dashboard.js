"use strict";
window.WorkbenchCampaigns=(()=>{
  let cfg,offset=0,request=0,summaryRequest=0,timer,snapshot=null,total=0,busy=false;
  const selected=new Set(),el=id=>document.getElementById(id),size=50;
  function filters(){const p=new URLSearchParams();for(const [key,id] of [['campaign_id','campaign-filter'],['state','campaign-outcome'],['market','campaign-market'],['deleted','campaign-deleted'],['search','campaign-search']]){const value=el(id).value;if(value)p.set(key,value);}return p;}
  const number=value=>Number(value||0).toLocaleString();
  function scope(){return snapshot.campaigns.find(c=>String(c.id)===el('campaign-filter').value);}
  function count(name){return Number((scope()||snapshot.totals)[name]||0);}
  function badge(label,tone='neutral'){return `<span class="campaign-badge ${tone}">${cfg.esc(label)}</span>`;}
  function panel(name){
    for(const section of document.querySelectorAll('[data-campaign-panel]'))section.hidden=section.dataset.campaignPanel!==name;
    for(const button of document.querySelectorAll('[data-campaign-view]'))button.setAttribute('aria-pressed',String(button.dataset.campaignView===name));
    if(name==='overview'&&snapshot)renderChart();
  }
  function focusOutcome(state,scroll=true){
    panel('prospects');
    el('campaign-outcome').value=state==='deleted'?'all':state;
    el('campaign-deleted').value=state==='deleted'?'deleted':'active';
    offset=0;selected.clear();syncTabs();loadRows();
    if(scroll)el('campaign-prospect-panel').scrollIntoView({block:'start',behavior:'smooth'});
  }
  function syncTabs(){
    const state=el('campaign-deleted').value==='deleted'?'deleted':el('campaign-outcome').value;
    for(const button of document.querySelectorAll('[data-outcome]'))button.setAttribute('aria-pressed',String(button.dataset.outcome===state));
  }
  function renderChart(){
    const rows=scope()?.trend||snapshot.analytics?.series||[];
    const peak=Math.ceil(Math.max(2,...rows.map(r=>Math.max(r.sent,r.replies)))/2)*2;
    const width=Math.max(260,el('campaign-chart').clientWidth||620),height=145,left=34,bottom=height-22,step=(width-left-12)/Math.max(rows.length,1);
    const lines=[0,.5,1].map(part=>{const y=bottom-part*100;return `<line x1="${left}" y1="${y}" x2="${width}" y2="${y}"/><text x="25" y="${y+4}" text-anchor="end">${number(Math.ceil(peak*part))}</text>`;}).join('');
    const bars=rows.map((r,i)=>{const x=left+step*i+step*.2,barWidth=Math.max(2,step*.28);return `<g><title>${cfg.esc(r.date)} UTC: ${r.sent} accepted, ${r.replies} reply events</title><rect class="chart-sent" x="${x}" y="${bottom-r.sent/peak*100}" width="${barWidth}" height="${r.sent/peak*100}" rx="2"/><rect class="chart-reply" x="${x+barWidth+2}" y="${bottom-r.replies/peak*100}" width="${barWidth}" height="${r.replies/peak*100}" rx="2"/>${i===0||i===4||i===8||i===rows.length-1?`<text x="${x}" y="${height-2}">${cfg.esc(r.date.slice(5))}</text>`:''}</g>`;}).join('');
    const sent=rows.reduce((n,r)=>n+r.sent,0),replies=rows.reduce((n,r)=>n+r.replies,0);
    el('campaign-chart').innerHTML=`<div class="chart-totals"><strong>${number(sent)}<span>accepted messages</span></strong><strong>${number(replies)}<span>reply events</span></strong></div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Last 14 days: ${sent} SMTP accepted messages and ${replies} reply events. Dates are UTC.">${lines}${bars}</svg><div class="chart-legend"><span><i></i>SMTP accepted</span><span><i></i>Replies</span>${sent||replies?'':'<span class="chart-empty">No sending or reply activity recorded in this period</span>'}</div>`;
  }
  function renderWork(){
    const items=[['Drafts to review','drafts','messages','drafts'],['Waiting in queue','queued','messages','queued'],['Submission needs review','uncertain','messages','attention'],['Research running','running_jobs','jobs','operations'],['Research pending','pending_jobs','jobs','operations'],['Research errors','failed_jobs','jobs','operations']];
    el('campaign-work-queue').innerHTML=items.map(([label,key,unit,target])=>`<button type="button" class="queue-row" data-queue-target="${target}"><span>${label}</span><strong>${number(count(key))}<small>${unit}</small></strong><span aria-hidden="true">↗</span></button>`).join('');
    for(const button of el('campaign-work-queue').querySelectorAll('button'))button.onclick=()=>button.dataset.queueTarget==='operations'?cfg.openOperations():focusOutcome(button.dataset.queueTarget);
    const activity=scope()?.activity||snapshot.analytics?.activity||[];
    const labels={sent:['Message accepted','success'],reply:['Reply received','success'],bounce:['Hard bounce','danger'],opt_out:['Opted out / do not contact','warning'],send_uncertain:['Submission uncertain','warning'],send_rejected:['Sending error','danger']};
    el('campaign-activity').innerHTML=activity.length?activity.map(item=>`<div class="activity-row"><span class="activity-dot ${labels[item.kind]?.[1]||'neutral'}"></span><div><strong>${cfg.esc(labels[item.kind]?.[0]||item.kind)}</strong><button type="button" data-activity-lead="${Number(item.lead_id)}">${cfg.esc(item.company)}</button></div><time datetime="${new Date(item.created_at*1000).toISOString()}">${cfg.stamp(item.created_at)}</time></div>`).join(''):'<div class="campaign-empty-activity"><span aria-hidden="true">◷</span><div><strong>No delivery activity yet</strong><p>Accepted messages, replies, bounces and opt-outs will appear here as they are recorded.</p></div></div>';
    for(const button of el('campaign-activity').querySelectorAll('button'))button.onclick=()=>cfg.openLead(Number(button.dataset.activityLead));
  }
  function targets(){if(!snapshot)return;for(const select of document.querySelectorAll('.campaign-target')){const form=select.form,goal=form.elements.campaign.value,previous=select.value;select.innerHTML='<option value="">Default campaign for this goal</option>'+snapshot.campaigns.filter(c=>c.goal===goal).map(c=>`<option value="${Number(c.id)}">${cfg.esc(c.name)}</option>`).join('');select.value=previous;if(!select.value)select.value='';}}
  function renderSummary(){
    const labels=[['Prospects','prospects',`${number(count('active_prospects'))} active records`,'all'],['Sent','sent','SMTP accepted messages','sent'],['Replied','replied','Current contact outcome','replied'],['Bounced','bounced','Current contact outcome','bounced'],['Opted out','unsubscribed','Unsubscribed / do not contact','unsubscribed'],['Deleted','deleted','Recoverable prospect records','deleted']];
    el('campaign-metrics').innerHTML=labels.map(([label,key,detail,outcome])=>`<button type="button" class="metric metric-${key}" data-metric-outcome="${outcome}"><span>${label}</span><strong>${number(count(key))}</strong><small>${detail}</small></button>`).join('');
    for(const button of el('campaign-metrics').querySelectorAll('button'))button.onclick=()=>focusOutcome(button.dataset.metricOutcome);
    el('campaign-note').textContent=snapshot.note;
    const current=el('campaign-filter').value,target=el('bulk-campaign').value;
    const options=snapshot.campaigns.map(c=>`<option value="${Number(c.id)}">${cfg.esc(c.name)} · ${c.goal}</option>`).join('');
    el('campaign-filter').innerHTML='<option value="">All campaigns</option>'+options;el('campaign-filter').value=current;
    el('bulk-campaign').innerHTML='<option value="">Choose destination campaign</option>'+options;el('bulk-campaign').value=target;
    el('campaign-count').textContent=snapshot.campaigns.length;
    el('campaign-cards').innerHTML=snapshot.campaigns.map(c=>`<tr class="${String(c.id)===current?'is-selected':''}"><td><button type="button" class="campaign-card-name" data-campaign-open="${Number(c.id)}">${cfg.esc(c.name)}</button><small>${c.goal==='A'?'Enquiries & bookings':'Ecommerce growth'} · ${number(c.contacts)} contacts</small></td><td>${badge(c.state==='paused'?'Paused':'Active',c.state==='paused'?'warning':'success')}</td><td><strong>${number(c.active_prospects)}</strong><small>${number(c.drafts)} drafts · ${number(c.queued)} queued</small></td>${['sent','replied','bounced','unsubscribed','deleted'].map(key=>`<td class="numeric">${number(c[key])}</td>`).join('')}<td><div class="campaign-row-actions"><button type="button" data-campaign-find="${Number(c.id)}">Find prospects</button><button type="button" data-campaign-toggle="${Number(c.id)}" data-state="${c.state==='paused'?'active':'paused'}">${c.state==='paused'?'Resume campaign':'Pause campaign'}</button></div></td></tr>`).join('');
    for(const button of document.querySelectorAll('[data-campaign-open]'))button.onclick=()=>{el('campaign-filter').value=button.dataset.campaignOpen;offset=0;selected.clear();renderSummary();loadRows();};
    for(const button of document.querySelectorAll('[data-campaign-find]'))button.onclick=()=>{const campaign=snapshot.campaigns.find(c=>c.id===Number(button.dataset.campaignFind));cfg.openDiscovery();const form=el('search-form');form.elements.campaign.value=campaign.goal;targets();form.elements.campaign_id.value=campaign.id;form.elements.query.focus();};
    for(const button of document.querySelectorAll('[data-campaign-toggle]'))button.onclick=async()=>{if(busy)return;button.disabled=true;try{const r=await cfg.api('/api/campaigns/'+button.dataset.campaignToggle,'PATCH',{state:button.dataset.state});cfg.notice(r.note);await refresh();}catch(e){cfg.notice(e.message,true);}finally{button.disabled=false;}};
    el('campaign-updated').textContent='Updated '+new Date((snapshot.generated_at||Date.now()/1000)*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
    el('campaign-list-heading').textContent=scope()?scope().name+' · prospects':'All prospects';
    renderChart();renderWork();syncTabs();targets();
  }
  function selection(){el('campaign-bulk-toolbar').hidden=!selected.size;el('campaign-selection').textContent=`${selected.size} selected on this page`;el('campaign-bulk-run').disabled=busy||!selected.size;const boxes=[...document.querySelectorAll('[data-campaign-select]')];for(const box of boxes)box.disabled=busy;el('campaign-select-page').disabled=busy;el('campaign-select-page').checked=!!boxes.length&&boxes.every(b=>b.checked);el('campaign-select-page').indeterminate=boxes.some(b=>b.checked)&&!el('campaign-select-page').checked;for(const button of document.querySelectorAll('[data-campaign-toggle]'))button.disabled=busy;el('campaign-new').disabled=busy;el('campaign-prev').disabled=busy||offset===0;el('campaign-next').disabled=busy||offset+size>=total;}
  async function loadRows(){
    const turn=++request,p=filters();p.set('limit',size);p.set('offset',offset);el('campaign-export').href='/api/campaign-export?'+filters();
    el('campaign-list-status').textContent='Loading prospects…';
    try{const data=await cfg.api('/api/campaign-prospects?'+p);if(turn!==request)return;total=data.total;const visible=new Set(data.rows.map(r=>r.id));for(const id of selected)if(!visible.has(id))selected.delete(id);
      el('campaign-rows').innerHTML=data.rows.map(r=>`<tr class="${selected.has(r.id)?'is-selected':''}"><td><input type="checkbox" data-campaign-select="${Number(r.id)}" aria-label="Select ${cfg.esc(r.company)}" ${selected.has(r.id)?'checked':''}></td><td><button type="button" class="campaign-open-prospect" data-campaign-prospect="${Number(r.id)}">${cfg.esc(r.company)}</button><small>${cfg.esc(r.domain.startsWith('profile:')?'Business profile':r.domain)} · ${cfg.esc(r.country||'Market unconfirmed')}</small></td><td>${cfg.esc(r.campaign_name)}<small>Goal ${cfg.esc(r.campaign)}</small></td><td>${cfg.esc(r.emails||'No contact found')}<small>${r.drafts?badge(number(r.drafts)+' draft'+(r.drafts===1?'':'s')+' to review','info'):cfg.esc(r.status.replaceAll('_',' '))}${r.deleted_at?' '+badge('DELETED','neutral'):''}</small></td><td class="numeric">${number(r.sent)}</td><td class="numeric">${number(r.queued)}${r.sending?`<small>${number(r.sending)} submitting</small>`:''}</td><td><div class="outcome-badges">${[['Bounced',r.bounced,'danger'],['Replied',r.replied,'success'],['Opted out',r.unsubscribed,'warning'],['Failed',r.failed,'danger'],['Uncertain',r.uncertain,'warning']].filter(([,n])=>n).map(([label,n,tone])=>badge(label+': '+number(n),tone)).join('')||'<span class="muted">No outcome yet</span>'}</div></td><td>${r.deleted_at?cfg.stamp(r.deleted_at):cfg.stamp(r.last_sent_at)}</td></tr>`).join('')||'<tr><td colspan="8"><div class="campaign-empty-list"><strong>No prospects match this view</strong><p>Try a different filter, or use Find prospects in your campaign to start research.</p><button type="button" id="campaign-empty-reset">Reset filters</button></div></td></tr>';
      if(el('campaign-empty-reset'))el('campaign-empty-reset').onclick=()=>el('campaign-clear-filters').click();
      el('campaign-list-status').textContent=total?`${offset+1}–${Math.min(offset+size,total)} of ${total} prospects`:'No prospects match these filters.';
      el('campaign-prev').disabled=busy||offset===0;el('campaign-next').disabled=busy||offset+size>=total;
      for(const box of document.querySelectorAll('[data-campaign-select]'))box.onchange=()=>{const id=Number(box.dataset.campaignSelect);if(box.checked)selected.add(id);else selected.delete(id);selection();};
      for(const button of document.querySelectorAll('[data-campaign-prospect]'))button.onclick=()=>cfg.openLead(Number(button.dataset.campaignProspect));
      selection();syncTabs();
    }catch(e){if(turn===request){el('campaign-list-status').textContent='Could not load campaign data: '+e.message;el('campaign-rows').innerHTML='';selected.clear();selection();}}
  }
  async function refresh(){const turn=++summaryRequest;try{const data=await cfg.api('/api/campaigns');if(turn!==summaryRequest)return;snapshot=data;renderSummary();await loadRows();}catch(e){if(turn===summaryRequest)cfg.notice('Campaign dashboard could not refresh: '+e.message,true);}}
  function actionFields(){const action=el('campaign-bulk-action').value;el('bulk-campaign-label').hidden=action!=='assign';el('bulk-reason-label').hidden=action!=='delete';el('bulk-confirm-label').hidden=action!=='delete';}
  function init(options){cfg=options;el('campaign-refresh').onclick=refresh;el('campaign-new').onclick=()=>{el('campaign-create').open=true;el('campaign-create').querySelector('input').focus();};
    window.addEventListener('resize',()=>{if(snapshot&&!el('campaigns').hidden)renderChart();});
    for(const button of document.querySelectorAll('[data-campaign-view]'))button.onclick=()=>panel(button.dataset.campaignView);
    el('campaign-create-cancel').onclick=()=>{el('campaign-create').open=false;el('campaign-new').focus();};
    for(const button of document.querySelectorAll('[data-outcome]'))button.onclick=()=>focusOutcome(button.dataset.outcome,false);
    el('campaign-clear-filters').onclick=()=>{for(const [id,value] of [['campaign-outcome','all'],['campaign-market',''],['campaign-deleted','active'],['campaign-search','']])el(id).value=value;offset=0;selected.clear();syncTabs();loadRows();};
    el('campaign-create-form').onsubmit=async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;try{const result=await cfg.api('/api/campaigns','POST',Object.fromEntries(new FormData(event.target)));event.target.reset();await refresh();el('campaign-filter').value=result.id;offset=0;selected.clear();renderSummary();await loadRows();el('campaign-create').open=false;cfg.notice('Campaign created. Add prospects directly or move unapproved prospects into it.');}catch(e){cfg.notice(e.message,true);}finally{button.disabled=false;}};
    for(const id of ['campaign-filter','campaign-outcome','campaign-market','campaign-deleted'])el(id).onchange=()=>{offset=0;selected.clear();if(snapshot)renderSummary();loadRows();};
    el('campaign-search').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{offset=0;selected.clear();loadRows();},250);};
    el('campaign-prev').onclick=()=>{offset=Math.max(0,offset-size);selected.clear();loadRows();};el('campaign-next').onclick=()=>{offset+=size;selected.clear();loadRows();};
    el('campaign-select-page').onchange=event=>{for(const box of document.querySelectorAll('[data-campaign-select]')){box.checked=event.target.checked;const id=Number(box.dataset.campaignSelect);if(box.checked)selected.add(id);else selected.delete(id);}selection();};
    el('campaign-bulk-action').onchange=actionFields;actionFields();
    el('campaign-bulk-run').onclick=async()=>{if(busy||!selected.size)return;const action=el('campaign-bulk-action').value,body={lead_ids:[...selected],action};if(action==='assign'){body.campaign_id=Number(el('bulk-campaign').value);if(!body.campaign_id){cfg.notice('Choose a destination campaign.',true);return;}}if(action==='delete'){body.reason=el('bulk-reason').value.trim();if(body.reason.length<3||!el('bulk-confirm').checked){cfg.notice('Add a reason and confirm deletion of the selected prospects.',true);return;}}
      busy=true;selection();try{const r=await cfg.api('/api/campaign-prospects/bulk','POST',body);el('campaign-bulk-results').innerHTML=`<p>${Number(r.succeeded)} of ${r.results.length} updated. ${cfg.esc(r.note)}</p>`+r.results.filter(row=>!row.ok).map(row=>`<p>Prospect #${Number(row.lead_id)}: ${cfg.esc(row.reason)}</p>`).join('');selected.clear();el('bulk-confirm').checked=false;await refresh();}catch(e){cfg.notice(e.message,true);}finally{busy=false;selection();}};
    for(const select of document.querySelectorAll('form select[name=campaign]'))select.addEventListener('change',targets);
  }
  async function loadTargets(){if(!snapshot){try{snapshot=await cfg.api('/api/campaigns');}catch(e){cfg.notice('Campaign choices unavailable: '+e.message,true);return;}}targets();}
  return {init,refresh,loadTargets};
})();
