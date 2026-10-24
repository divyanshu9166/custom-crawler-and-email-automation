"use strict";
window.WorkbenchSettings=(()=>{
  let cfg,request=0,offlineDemo=false,writerBusy=false,savedWriter=null;const el=id=>document.getElementById(id);
  function populateRuntime(s){
    const form=el('runtime-settings-form');
    for(const name of ['worker_enabled','sending_enabled'])form.elements[name].checked=!!s[name];
    if(s.demo!==undefined)offlineDemo=!!s.demo;
    for(const input of form.querySelectorAll('input,button'))input.disabled=offlineDemo;
    el('runtime-summary').textContent=offlineDemo?'Offline demo: automation and sending cannot be enabled.':`Worker ${s.worker_enabled?'ON':'OFF'} · Sending ${s.sending_enabled?'ON':'OFF'}${s.paused===true?' · paused':''}`;
  }
  function populateResearch(s){const form=el('research-settings-form');for(const input of form.elements){if(!input.name)continue;if(input.type==='checkbox')input.checked=!!s[input.name];else if(s[input.name]!==undefined)input.value=s[input.name];}}
  function populatePageSpeed(s){
    const form=el('pagespeed-settings-form'),input=form.elements.pagespeed_api_key;
    input.value='';input.placeholder=s.pagespeed_api_key_configured?'Saved · leave blank to keep':'Not configured';
    form.elements.clear_pagespeed_api_key.checked=false;
    el('pagespeed-secret-status').textContent=s.pagespeed_api_key_configured?'An API key is saved. Its value is never displayed.':'No PageSpeed API key saved yet.';
  }
  let mailboxes=[],editingMailbox='new';
  function mailboxRow(m,u){
    const usage=u?`${u.used_24h??0}/${m.daily_limit} today · ${u.used_1h??0}/${m.hourly_limit} this hour · catch-all ${u.catch_all_24h??0}/${u.catch_all_cap??0} · inbox ${u.inbox_current?'current':'not current'}${u.inbox_error?' ('+cfg.esc(u.inbox_error)+')':''}`:`${m.daily_limit}/day · ${m.hourly_limit}/hour`;
    const status=!m.configured?' · incomplete':m.enabled===false?' · paused':!m.domain_confirmed?' · not sending: confirm SPF/DKIM/DMARC for '+cfg.esc(m.domain):m.sending===false?' · not sending':' · sending';
    return `<div class="item"><strong>${cfg.esc(m.primary?'Primary mailbox':(m.label||m.sender_email||'Mailbox'))}</strong> <span class="small">${cfg.esc(m.sender_email||'not configured')}${m.alias?' · alias (shares its login\'s limits)':''}${status}</span><p class="small">${usage}</p>${m.primary?'':`<button type="button" data-mailbox-edit="${cfg.esc(m.id)}">Edit</button> <button type="button" data-mailbox-remove="${cfg.esc(m.id)}">Remove</button>`}</div>`;
  }
  function dnsSummary(d){const c=d.dns_check;if(!c)return '<p class="small">DNS not checked yet.</p>';const parts=[['SPF',c.spf?.ok],['DKIM',c.dkim?.ok],['DMARC',c.dmarc?.ok],['MX',c.mx?.ok]].map(([n,ok])=>`${n} ${ok?'✓':'✗'}`).join(' · ');const lists=(c.blocklists||[]).map(b=>`${cfg.esc(b.list)}: ${cfg.esc(b.state)}`).join(' · ');const warn=d.auth_confirmed&&!c.ready?'<p class="error">Marked as authenticated, but the DNS check does not pass.</p>':'';return `<p class="${c.ready?'small':'error'}">${c.ready?'DNS ready':'DNS not ready'} · ${parts} · ${lists} · checked ${new Date(c.checked_at*1000).toLocaleString()}</p>`+warn+((c.issues||[]).length?'<ul>'+c.issues.map(i=>`<li>${cfg.esc(i)}</li>`).join('')+'</ul>':'');}
  async function populateMailboxes(list){
    if(list)mailboxes=list;const usage={};let domainUsage=[];
    try{const d=await cfg.api('/api/delivery');for(const m of d.mailboxes||[])usage[m.id]=m;domainUsage=d.domains||[];}catch(_){}
    el('mailbox-list').innerHTML=mailboxes.map(m=>mailboxRow(m,usage[m.id])).join('')||'<p>No mailbox configured yet.</p>';
    el('domain-list').innerHTML=(domainUsage||[]).map(d=>`<form class="item" data-domain-cap="${cfg.esc(d.domain)}"><strong>${cfg.esc(d.domain)}</strong> <span class="small">${d.mailboxes} mailbox(es) · ${d.auth_confirmed?'SPF/DKIM/DMARC confirmed':'not confirmed: its mailboxes do not send'} · ${d.used_24h??0} sent in 24 h</span> <label>Daily cap<input name="daily_cap" type="number" min="0" max="5000" value="${Number(d.daily_cap)||0}"></label> <button type="submit">Save cap</button> <label>DKIM selector (optional)<input name="dkim_selector" maxlength="63" pattern="[A-Za-z0-9._-]*" placeholder="auto"></label> <button type="button" data-domain-check="${cfg.esc(d.domain)}">Check DNS</button>${dnsSummary(d)}</form>`).join('')||'<p class="small">No sender domains yet.</p>';
  }
  function editMailbox(id){
    const f=el('mailbox-form'),m=mailboxes.find(x=>x.id===id&&!x.primary);editingMailbox=m?id:'new';f.reset();
    for(const input of f.elements){if(!input.name)continue;if(input.type==='password'){input.value='';input.placeholder=m&&m[input.name+'_configured']?'Saved · leave blank to keep':'Not configured';}else if(m&&input.type==='checkbox')input.checked=m[input.name]!==false;else if(m&&m[input.name]!==undefined&&m[input.name]!==null)input.value=m[input.name];}
    el('mailbox-editor-title').textContent=m?'Edit '+(m.label||m.sender_email):'Add a mailbox';el('mailbox-editor').open=!!m;
  }
  function populate(s){if(s.mailboxes)populateMailboxes(s.mailboxes);populatePageSpeed(s);if(s.draft_model!==undefined)savedWriter={url:s.draft_api_url,model:s.draft_model,timeout:s.draft_timeout_seconds};if(!writerBusy&&'writer_last_check' in s){el('writer-test-result').textContent=s.writer_last_check?'Last test: '+s.writer_last_check.note:'';el('writer-test-result').className=s.writer_last_check?.state==='failed'?'error':'';}populateRuntime(s);populateResearch(s);const f=el('mail-settings-form');for(const input of f.elements){if(!input.name)continue;if(input.type==='password'){input.value='';input.placeholder=s[input.name+'_configured']?'Saved · leave blank to keep':'Not configured';}else if(input.type==='checkbox'){input.checked=!!s[input.name];}else if(s[input.name]!==undefined)input.value=s[input.name];}const w=el('writer-settings-form');for(const input of w.elements){if(input.name==='draft_api_key'){input.value='';input.placeholder=s.draft_api_key_configured?'Saved · leave blank to keep':'Not configured';}else if(input.name==='clear_draft_api_key')input.checked=false;else if(s[input.name]!==undefined)input.value=s[input.name];}el('writer-secret-status').textContent=s.draft_api_key_configured?'An API key is saved. Its value is never displayed.':'No API key saved yet.';el('credentials-form').elements.username.value=s.admin_user;for(const protocol of ['smtp','imap'])el(protocol+'-secret-status').textContent=s[protocol+'_password_configured']?'A password is saved. Its value is never displayed.':'No password saved yet.';el('settings-readiness').innerHTML=`<span class="eyebrow">CONNECTION READINESS</span><h3>${s.sending_enabled?(s.sending_gaps.length?'Setup incomplete':'Configuration ready'):'Sending disabled'}</h3><p>Workspace: ${cfg.esc(s.public_url)}</p>${s.sending_gaps.length?`<p>Sending setup is separate from drafting.</p><details><summary>Sending setup checklist</summary><ul>${s.sending_gaps.map(g=>`<li>${cfg.esc(g.replaceAll('_',' '))}</li>`).join('')}</ul></details>`:'<p>Configuration fields are present. Actual provider and domain checks still need to pass.</p>'}`;}
  async function load(){const turn=++request;try{const s=await cfg.api('/api/settings');if(turn===request)populate(s);}catch(e){cfg.notice('Settings could not load: '+e.message,true);}}
  function init(options){cfg=options;const mail=el('mail-settings-form'),account=el('credentials-form');mail.onsubmit=async e=>{e.preventDefault();const button=mail.querySelector('button[type=submit]'),result=el('mail-settings-result');button.disabled=true;result.className='';result.textContent='Saving…';const body=Object.fromEntries(new FormData(mail));for(const name of ['domain_auth_confirmed','clear_smtp_password','clear_imap_password'])body[name]=mail.elements[name].checked;for(const name of ['smtp_port','imap_port','daily_send_limit','hourly_send_limit','min_send_interval_seconds','send_hour_start','send_hour_end','catch_all_share'])body[name]=Number(body[name]);try{const s=await cfg.api('/api/settings/mail','PUT',body);populate(s);result.textContent='Email settings saved. Sending is paused; the provider connection remains unverified.';cfg.refresh().catch(e=>cfg.notice('Saved. Dashboard refresh failed: '+e.message,true));}catch(e){result.textContent=e.message;result.className='error';}finally{button.disabled=false;}};
    const pagespeed=el('pagespeed-settings-form');pagespeed.onsubmit=async e=>{
      e.preventDefault();const button=pagespeed.querySelector('button[type=submit]'),result=el('pagespeed-settings-result');
      button.disabled=true;result.className='';result.textContent='Saving…';
      const body={pagespeed_api_key:pagespeed.elements.pagespeed_api_key.value.trim(),clear_pagespeed_api_key:pagespeed.elements.clear_pagespeed_api_key.checked};
      try{const saved=await cfg.api('/api/settings/pagespeed','PUT',body);populatePageSpeed(saved);result.textContent=saved.pagespeed_api_key_configured?'PageSpeed key saved. Open a prospect and run PageSpeed audit.':'PageSpeed key is not configured. Audits may be limited by provider quota.';cfg.refresh().catch(e=>cfg.notice('Saved. Dashboard refresh failed: '+e.message,true));}
      catch(e){result.textContent=e.message;result.className='error';}finally{button.disabled=false;}
    };
    const research=el('research-settings-form');research.onsubmit=async e=>{
      e.preventDefault();const body={},result=el('research-settings-result'),button=research.querySelector('button');
      for(const input of research.elements){if(input.name)body[input.name]=input.type==='checkbox'?input.checked:Number(input.value);}
      button.disabled=true;result.textContent='Saving…';
      try{const saved=await cfg.api('/api/settings/research','PUT',body);populateResearch(saved);result.textContent='Research controls saved. Sending is paused.';cfg.refresh().catch(e=>cfg.notice(e.message,true));}
      catch(e){result.textContent=e.message;}finally{button.disabled=false;}
    };
    const runtime=el('runtime-settings-form');runtime.onsubmit=async e=>{
      e.preventDefault();const result=el('runtime-settings-result'),button=runtime.querySelector('button[type=submit]');
      const body={worker_enabled:runtime.elements.worker_enabled.checked,sending_enabled:runtime.elements.sending_enabled.checked};
      button.disabled=true;result.className='';result.textContent='Saving…';
      try{const saved=await cfg.api('/api/settings/runtime','PUT',body);populateRuntime(saved);result.textContent='Automation controls saved. Sending is paused; use Resume sending when ready.';cfg.refresh().catch(e=>cfg.notice('Saved. Dashboard refresh failed: '+e.message,true));}
      catch(e){result.textContent=e.message;result.className='error';}
      finally{button.disabled=false;}
    };
    const writer=el('writer-settings-form');writer.onsubmit=async e=>{e.preventDefault();if(writerBusy)return;writerBusy=true;el('writer-test').disabled=true;const result=el('writer-settings-result'),button=writer.querySelector('button[type=submit]');const body=Object.fromEntries(new FormData(writer));body.clear_draft_api_key=writer.elements.clear_draft_api_key.checked;body.draft_timeout_seconds=Number(body.draft_timeout_seconds);button.disabled=true;result.className='';result.textContent='Saving…';try{const s=await cfg.api('/api/settings/writer','PUT',body);populate(s);result.textContent='AI writer settings saved. No provider call made; sending remains paused.';el('writer-test-result').textContent='Connection test needed for this saved configuration.';cfg.refresh().catch(e=>cfg.notice('Saved. Dashboard refresh failed: '+e.message,true));}catch(e){result.textContent=e.message;result.className='error';}finally{button.disabled=false;writerBusy=false;el('writer-test').disabled=false;}};
    el('writer-nvidia').onclick=()=>{writer.elements.draft_api_url.value='https://integrate.api.nvidia.com/v1';writer.elements.draft_model.value='nvidia/nemotron-3-ultra-550b-a55b';writer.elements.draft_timeout_seconds.value=180;el('writer-settings-result').className='';el('writer-settings-result').textContent='NVIDIA values filled. API key unchanged. Save settings, then test the connection.';cfg.notice(el('writer-settings-result').textContent);};
    el('writer-test').onclick=async()=>{
      if(writerBusy)return;
      if(savedWriter&&(writer.elements.draft_model.value!==savedWriter.model||writer.elements.draft_api_url.value!==savedWriter.url||Number(writer.elements.draft_timeout_seconds.value)!==savedWriter.timeout||writer.elements.draft_api_key.value||writer.elements.clear_draft_api_key.checked)){const r=el('writer-test-result');r.textContent='Unsaved AI settings. Click Save AI writer settings first, then test the saved key/model.';r.className='error';r.scrollIntoView({block:'nearest'});cfg.notice(r.textContent,true);return;}
      writerBusy=true;
      const b=el('writer-test'),r=el('writer-test-result'),save=writer.querySelector('button[type=submit]'),preset=el('writer-nvidia');
      const started=Date.now(),controller=new AbortController();let deadline;
      b.disabled=save.disabled=preset.disabled=true;r.className='';
      function progress(){const seconds=Math.floor((Date.now()-started)/1000);b.textContent=`Testing… ${seconds}s`;r.textContent=`Testing saved AI key/model… ${seconds}s elapsed. The server test has a 65-second limit. No prospect data or email is sent.`;}
      progress();r.scrollIntoView({block:'nearest'});const ticking=setInterval(progress,1000);
      try{
        const timeout=new Promise((_,reject)=>{deadline=setTimeout(()=>{reject(new Error('AI test exceeded 75 seconds waiting for the server/tunnel. Key validity is unknown. The earlier request may still finish; check the last test result before retrying.'));controller.abort();},75000);});
        const v=await Promise.race([cfg.api('/api/providers/writer/test','POST',undefined,{signal:controller.signal}),timeout]);
        r.textContent=(v.model?'Model: '+v.model+' · ':'')+v.note;r.className=v.ready?'':'warn';
      }catch(e){r.textContent=e.message;r.className='error';}
      finally{clearInterval(ticking);clearTimeout(deadline);writerBusy=false;b.disabled=save.disabled=preset.disabled=false;b.textContent='Test AI connection';}
    };
    const boxForm=el('mailbox-form');
    boxForm.onsubmit=async e=>{e.preventDefault();const result=el('mailbox-result'),button=boxForm.querySelector('button[type=submit]');const body=Object.fromEntries(new FormData(boxForm));for(const n of ['enabled','alias','domain_auth_confirmed'])body[n]=boxForm.elements[n].checked;for(const n of ['smtp_port','imap_port','daily_limit','hourly_limit'])body[n]=Number(body[n]);for(const n of ['smtp_password','imap_password'])if(!body[n])delete body[n];button.disabled=true;result.className='';result.textContent='Saving…';
      try{const s=await cfg.api('/api/settings/mailboxes/'+encodeURIComponent(editingMailbox),'PUT',body);await populateMailboxes(s.mailboxes);editMailbox('new');result.textContent='Mailbox saved. Sending is paused; the connection is checked when its inbox is next polled.';}
      catch(err){result.textContent=err.message;result.className='error';}finally{button.disabled=false;}};
    el('mailbox-cancel').onclick=()=>editMailbox('new');
    el('domain-list').onclick=async e=>{const b=e.target.closest('[data-domain-check]'),result=el('mailbox-result');if(!b)return;const f=b.closest('form');b.disabled=true;result.className='';result.textContent='Checking public DNS for '+b.dataset.domainCheck+'…';try{const r=await cfg.api('/api/deliverability/check','POST',{domain:b.dataset.domainCheck,dkim_selector:f.elements.dkim_selector.value.trim()});await populateMailboxes();result.textContent=r.ready?'DNS ready for '+r.domain+'.':'DNS not ready for '+r.domain+': '+r.issues.length+' issue(s) listed below.';result.className=r.ready?'':'error';}catch(err){result.textContent=err.message;result.className='error';}finally{b.disabled=false;}};
    el('domain-list').onsubmit=async e=>{e.preventDefault();const f=e.target.closest('[data-domain-cap]'),result=el('mailbox-result');if(!f)return;try{const s=await cfg.api('/api/settings/domain-caps','PUT',{domain:f.dataset.domainCap,daily_cap:Number(f.elements.daily_cap.value)||0});await populateMailboxes(s.mailboxes);result.className='';result.textContent='Domain cap saved. Sending is paused.';}catch(err){result.textContent=err.message;result.className='error';}};
    el('mailbox-list').onclick=async e=>{const edit=e.target.closest('[data-mailbox-edit]'),remove=e.target.closest('[data-mailbox-remove]'),result=el('mailbox-result');
      if(edit)editMailbox(edit.dataset.mailboxEdit);
      if(remove&&confirm('Remove this mailbox? Its sent history is kept.')){try{const s=await cfg.api('/api/settings/mailboxes/'+encodeURIComponent(remove.dataset.mailboxRemove),'DELETE');await populateMailboxes(s.mailboxes);result.className='';result.textContent='Mailbox removed. Sending is paused.';}catch(err){result.textContent=err.message;result.className='error';}}};
    account.onsubmit=async e=>{e.preventDefault();const result=el('credentials-result'),button=account.querySelector('button');const body=Object.fromEntries(new FormData(account));if(body.new_password!==body.confirm_password){result.textContent='The new passwords do not match.';cfg.notice(result.textContent,true);return;}delete body.confirm_password;button.disabled=true;result.className='';result.textContent='Updating sign-in details…';try{await cfg.api('/api/settings/credentials','PUT',body);account.reset();location.replace('/');}catch(e){result.textContent=e.message;result.className='error';button.disabled=false;}};
  }return {init,load};
})();
