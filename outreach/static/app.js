"use strict";
let currentId = null;
let detailRequest = 0;
let allLeads = [];
let pipelineRefreshInFlight = false;
let researchRunning = false;
let preparationTimer=null, detailDirty=false, prepBatchAfter=0;
let researchActivityTimer=null, researchActivityRequest=0;
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const stamp = value => value ? new Date(Number(value) * 1000).toLocaleString() : "—";
const link = url => /^https?:\/\//i.test(url || "") ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a>` : esc(url);
function notice(text, bad=false){$("#notice").textContent=text;$("#notice").className=bad?"error":"";window.WorkbenchFeedback.notice(text,bad);}
async function api(path, method="GET", payload, options={}){
  const feedback=options.feedback===false?null:window.WorkbenchFeedback.begin(path,method);
  try{
    const response=await fetch(path,{method,headers:payload?{"Content-Type":"application/json"}:{},body:payload?JSON.stringify(payload):undefined,signal:options.signal});
    let result;try{result=await response.json();}catch{throw new Error(`Unexpected server response (HTTP ${response.status}). Check the app/tunnel connection.${method==='GET'?'':' Request status is unknown; check the saved result or Operations before repeating it.'}`);}
    if(!response.ok){const error=new Error(typeof result.detail==='string'?result.detail:Array.isArray(result.detail)?result.detail.map(v=>(v.loc||[]).filter(k=>k!=='body').join('.')+': '+v.msg).join('; '):'The request could not be completed.');error.status=response.status;throw error;}
    if(feedback)window.WorkbenchFeedback.finish(feedback,result);
    return result;
  }catch(error){
    if(error instanceof TypeError)error=new Error(method==='GET'?'Connection unavailable. Displayed information may be outdated.':'Connection interrupted. Request status is unknown; it may already have been accepted. Check the saved result or Operations before repeating it.');
    if(error.name==='AbortError')error=new Error('Stopped waiting for the response. The server may still finish the request; check its result before retrying.');
    if(feedback)window.WorkbenchFeedback.fail(feedback,error);
    throw error;
  }
}
async function act(fn, message="Saved") {
  const release=window.WorkbenchFeedback.action();
  try{
    notice("Working…");
    let result;try{result=await fn();}catch(error){notice(error.message,true);return;}
    const text=typeof message==='function'?message(result):message;
    try{await refresh();}catch(error){notice(`${text} Dashboard refresh failed: ${error.message}`,true);return;}
    notice(text);
  }finally{release();}
}
function view(name){document.querySelectorAll(".view").forEach(el=>el.hidden=el.id!==name);document.querySelectorAll("nav button").forEach(el=>el.classList.toggle("selected",el.dataset.view===name));if(name==='campaigns'){history.replaceState(null,'','#campaigns');window.WorkbenchCampaigns.refresh();}else if(location.hash==='#campaigns')history.replaceState(null,'',location.pathname+location.search);if(name==="pipeline")refreshPipeline();if(name==="operations")operations();if(name==="discovery"){schedules();window.WorkbenchCampaigns.loadTargets();}if(name==="workflow")window.WorkbenchFlow.refresh();if(name==="settings")window.WorkbenchSettings.load();if(name==="learning")loadLearning();}

window.WorkbenchFeedback.init({api,view,workerEnabled:()=>researchRunning,completed:async()=>{await refresh({reloadDetail:false});await window.WorkbenchCampaigns.refresh();},openLead:id=>{view('pipeline');loadLead(id).catch(e=>notice(e.message,true));}});
document.querySelectorAll("nav button").forEach(button=>button.onclick=()=>view(button.dataset.view));
$("#start-discovery").onclick=()=>view("discovery");
$("#pipeline-find").onclick=()=>view("discovery");
$("#worker-control").onclick=()=>{view("settings");$("#runtime-settings-form").scrollIntoView({block:"start"});};
$("#pause").onclick=()=>act(()=>api("/api/pause","POST"),"Sending paused. An already submitted message cannot be recalled.");
$("#resume").onclick=()=>act(()=>api("/api/resume","POST"),"Sending resumed; only approved eligible sequences can send.");
$("#logout").onclick=async()=>{try{await api('/api/logout','POST');location.replace('/');}catch(e){notice(e.message,true);}};
$('#prepare-batch').onclick=async()=>{notice('Queuing preparation…');try{const r=await api('/api/preparation/batch?after_id='+prepBatchAfter,'POST');prepBatchAfter=r.next_after_id||0;$('#prepare-batch').textContent=prepBatchAfter?'Prepare next batch':'Prepare pending emails';notice(`${r.queued.length} preparation jobs queued; ${r.skipped.length} prospects need attention. Sending unchanged.`);$('#preparation-batch-report').hidden=false;$('#preparation-batch-results').innerHTML=[...r.queued.map(v=>({...v,reason:'Preparation queued.'})),...r.skipped].map(v=>`<p class="small"><button data-batch-lead="${Number(v.lead_id)}" type="button">Lead ${Number(v.lead_id)}</button> ${esc(v.reason)}</p>`).join('')||'<p>No eligible prospects on this page.</p>';document.querySelectorAll('[data-batch-lead]').forEach(b=>b.onclick=()=>loadLead(Number(b.dataset.batchLead)).catch(e=>notice(e.message,true)));}catch(e){notice(e.message,true);}};
$('#preparation-filter').onchange=renderLeads;
$("#refresh").onclick=()=>refresh().catch(e=>notice(e.message,true));
$("#learning-refresh").onclick=loadLearning;
$("#filter").oninput=renderLeads;
$("#lead-sort").onchange=renderLeads;
function formObject(form){const value=Object.fromEntries(new FormData(form));if('campaign_id' in value){if(value.campaign_id)value.campaign_id=Number(value.campaign_id);else delete value.campaign_id;}if('profile_first' in value)value.profile_first=value.profile_first==='true';return value;}
$("#search-form").onsubmit=event=>{event.preventDefault();const obj=formObject(event.target);obj.limit=Number(obj.limit);const recurring=!!obj.interval_hours;if(recurring)obj.interval_hours=Number(obj.interval_hours);else delete obj.interval_hours;act(()=>api(recurring?"/api/schedules":"/api/discover","POST",obj),recurring?"Recurring research scheduled.":"Search queued.").then(schedules);};
$('#google-business-form').onsubmit=event=>{event.preventDefault();const obj={...formObject(event.target),campaign:'A',profile_first:true,discovery_source:'google_maps'};obj.limit=Number(obj.limit);const recurring=!!obj.interval_hours;if(recurring)obj.interval_hours=Number(obj.interval_hours);else delete obj.interval_hours;act(()=>api(recurring?'/api/schedules':'/api/discover','POST',obj),recurring?'Campaign 3 Google business search scheduled.':'Campaign 3 Google business research queued.').then(()=>{schedules();window.WorkbenchCampaigns.loadTargets();});};
$("#profile-lead-form").onsubmit=event=>{event.preventDefault();act(()=>api("/api/profile-leads","POST",formObject(event.target)),"Business profile queued for research.");};
$("#browser-reference-form").onsubmit=event=>{event.preventDefault();const value=formObject(event.target);value.observed_at=new Date(value.observed_at).getTime()/1000;value.public_business_confirmed=event.target.elements.public_business_confirmed.checked;act(()=>api('/api/browser-references','POST',value),'Business reference saved. Check the company research queue.');};
$("#browser-reference-form").elements.observed_at.value=new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16);
$("#lead-form").onsubmit=event=>{event.preventDefault();act(()=>api("/api/leads","POST",{...formObject(event.target),source_url:event.target.elements.source_url.value||event.target.elements.website.value}),"Company queued for research.");};
$("#csv-form").onsubmit=event=>{event.preventDefault();act(async()=>{const file=$("#csv-file").files[0];if(!file)throw new Error('Choose a CSV file before importing.');if(file.size>1_000_000)throw new Error("CSV must be under 1 MB");const result=await api("/api/import","POST",{content:await file.text()});$("#import-result").textContent=JSON.stringify(result,null,2);return result;},result=>`Import processed: ${result.ids.length} rows accepted; ${result.errors.length} rows need attention. Review row details below.`);};
async function connectorReferences(){
  const file=$("#connector-file").files[0];
  if(!file||file.size>1_000_000)throw new Error("Choose a connector JSON export under 1 MB.");
  const data=JSON.parse(await file.text());
  if(data.format!=="outreach-business-references-v1"||!Array.isArray(data.references)||!data.references.length||data.references.length>100)throw new Error("Use a connector export with 1–100 references.");
  const keys=['company','source_url','website','observed_at','observation','capture_method'];
  for(const r of data.references)if(!r||typeof r!=='object'||Object.keys(r).some(k=>!keys.includes(k))||r.capture_method!=='browser_connector_reference')throw new Error("Unexpected connector reference fields.");
  return data.references;
}
$("#connector-file").onchange=async()=>{try{const refs=await connectorReferences();$("#connector-preview").innerHTML=refs.map(r=>`<div class="item"><strong>${esc(r.company)}</strong><p>${link(r.source_url)} · ${stamp(r.observed_at)}</p><p>Website candidate: ${link(r.website)}</p><p>${esc(r.observation)}</p></div>`).join('');}catch(e){$("#connector-preview").textContent=e.message;}};
$("#connector-import-form").onsubmit=event=>{event.preventDefault();const form=event.target;act(async()=>{
  if(!form.elements.confirmed.checked)throw new Error("Review the references before importing.");
  const refs=await connectorReferences(),result={imported:[],errors:[]};
  for(const [index,r] of refs.entries()){try{const saved=await api('/api/browser-references','POST',{...r,campaign:form.elements.campaign.value,country_hint:form.elements.country_hint.value,public_business_confirmed:true});result.imported.push({row:index+1,company:r.company,...saved});}catch(e){result.errors.push({row:index+1,company:r.company,error:e.message});}}
  $("#connector-result").textContent=JSON.stringify(result,null,2);return result;
},result=>`Connector import processed: ${result.imported.length} references accepted; ${result.errors.length} rows need attention. Review row details below.`);};
function renderSourceCoverage(coverage){
  const rows=coverage?.rows||[];
  $("#discovery-source-coverage").innerHTML=rows.length?`<div class="source-coverage-scroll"><table><thead><tr><th>Source</th><th>Signals</th><th>Captured</th><th>Unavailable / stale</th><th>Website candidates</th><th>Recovered via independent sources</th><th>Published email candidates</th></tr></thead><tbody>${rows.map(r=>`<tr><th>${esc(r.source)}</th><td>${Number(r.signals)}</td><td>${Number(r.captured)}</td><td>${Number(r.unavailable)}</td><td>${Number(r.website_candidates)}</td><td>${Number(r.failover_candidates)}</td><td>${Number(r.published_email_candidates)}</td></tr>`).join('')}</tbody></table></div><p class="small">${esc(coverage.scope)}. ${esc(coverage.note)}</p>`:'<p>No platform capture observations recorded yet. Search-run failures remain visible in Workflow → Recent search runs.</p>';
}
async function refresh({reloadDetail=true,includeDiagnostics=true,includePipeline=true}={}){
  const selectedAtStart=currentId;
  const diagnostics=includeDiagnostics?Promise.allSettled([api('/api/source-coverage'),api('/api/source-status')]):null;
  const [status, leads]=await Promise.all([api("/api/status"),includePipeline?api("/api/leads"):Promise.resolve(allLeads)]);allLeads=leads;
  $("#platform-browser-mode").hidden=!status.platform_browser_enabled;
  $("#fxembed-mode").hidden=!status.fxembed_profiles_enabled;
  $("#fxembed-mode").textContent="X bio research uses the free FxEmbed community source. Returned emails are candidates; current publication, inbox ownership and buyer relevance need review.";
  $("#platform-browser-mode").textContent="VPS browser discovery is enabled. "+(status.platform_browser_public_fallback?"Free public search and independent company pages remain available when the platform is held or its website link is missing. ":"Public-source failover is disabled. ")+(Object.keys(status.platform_browser_holds||{}).length?"Operator attention needed: "+JSON.stringify(status.platform_browser_holds):"Sources, business identity and contact ownership still require review.");
  researchRunning=!!status.worker_enabled;
  $("#mode").textContent=status.demo?"Offline demo · fictional prospects":!status.sending_enabled?"Sending off":status.paused?"Sending paused":"Sending enabled";
  $('#campaign-send-status').textContent=!status.sending_enabled?'● Sending off':status.paused?'● Sending paused':'● Sending enabled';
  $('#campaign-send-status').dataset.state=!status.sending_enabled?'off':status.paused?'paused':'enabled';
  $('#campaign-send-status').title='Campaign resume and bulk preparation never override global sending controls, approval or mailbox limits.';
  $("#worker-control").textContent=`Research: ${status.worker_enabled?'ON':'OFF'}`;
  $("#resume").disabled=!!status.demo||!status.worker_enabled||!status.sending_enabled;
  $("#resume").title=status.demo?'Offline demo':(!status.worker_enabled||!status.sending_enabled)?'Enable worker and sending in Settings first':'Resume approved eligible sequences';
  const sent=status.messages.find(x=>x.state==="sent")?.n||0;
  $("#metrics").innerHTML=[["Prospects",status.counts.leads],["Emails to review",leads.filter(l=>l.initial_email_state==='draft').length],["Contacts found",status.counts.contacts],["Emails sent",sent]].map(([label,n])=>`<div class="metric"><span>${label}</span><strong>${n}</strong></div>`).join("");
  renderLeads();if(reloadDetail&&currentId&&currentId===selectedAtStart)await loadLead(currentId);
  if(!diagnostics)return;
  const [coverage,sourceStatus]=await diagnostics;
  if(coverage.status==='fulfilled')renderSourceCoverage(coverage.value);
  else $('#discovery-source-coverage').textContent='Source coverage unavailable: '+coverage.reason.message;
  if(sourceStatus.status==='fulfilled')renderSourceStatus(sourceStatus.value);
  else $('#provider-source-status').textContent='Source diagnostics unavailable: '+sourceStatus.reason.message;
}
async function refreshPipeline(){
  if(pipelineRefreshInFlight)return;
  pipelineRefreshInFlight=true;
  try{await refresh({reloadDetail:false,includeDiagnostics:false});}
  catch(error){notice('Pipeline update failed; displayed data may be outdated: '+error.message,true);}
  finally{pipelineRefreshInFlight=false;}
}
function leadState(l){
  if(['pending','running'].includes(l.source_job?.state))return [window.WorkbenchWorkspace.researchLabel(l.source_job),'working'];
  if(l.initial_email_state==='draft'||l.preparation_state==='drafts_ready')return ['Draft saved','ready'];
  if(['pending','running'].includes(l.preparation_job))return ['Preparing email','working'];
  if(['needs_attention','needs_evidence'].includes(l.preparation_state)||l.status==='research_failed'||['failed','cancelled'].includes(l.source_job?.state))return ['Needs attention','attention'];
  if(l.status==='researching')return ['Research status needs checking','attention'];
  return [l.status==='qualified'?'Ready to draft':l.status==='new'?'Not researched yet':'Research saved','neutral'];
}
function renderLeads(){
  const listScroll=$('#leads').scrollTop;
  const query=$('#filter').value.toLowerCase();
  const rows=[...allLeads].sort((a,b)=>$('#lead-sort').value==='newest'?b.id-a.id:$('#lead-sort').value==='company'?a.company.localeCompare(b.company):0).filter(l=>{
    const p=$('#preparation-filter').value, state=leadState(l)[1];
    return (p==='all'||p==='ready'&&state==='ready'||p==='pending'&&state==='working'||p==='attention'&&state==='attention')&&(l.company+' '+l.domain+' '+l.status+' '+leadState(l)[0]).toLowerCase().includes(query);
  });
  $('#leads').innerHTML=rows.map(l=>{const [label,state]=leadState(l);return `<button class="lead ${l.id===currentId?'current':''}" data-lead="${l.id}"><span class="company-monogram" aria-hidden="true">${esc(l.company.trim().charAt(0).toUpperCase())}</span><span class="lead-info"><strong>${esc(l.company)}</strong><small>${esc(l.lead_kind==='profile'?'Business profile':l.domain)}</small><span class="lead-state ${state}"><i></i>${label}</span></span></button>`;}).join('')||`<div class="list-empty">${allLeads.length?'No prospects match these filters.':'No prospects yet. Start with Find prospects.'}</div>`;
  document.querySelectorAll('[data-lead]').forEach(b=>b.onclick=()=>loadLead(Number(b.dataset.lead)).catch(e=>notice(e.message,true)));
  $('#leads').scrollTop=listScroll;
}
const options = (values, selected) => values.map(v=>`<option value="${esc(v)}" ${v===selected?"selected":""}>${esc(v === "ai_calling_agent" ? "AI calling agent" : v.replaceAll("_"," "))}</option>`).join("");
function preparationHTML(data,finding){
  const p=data.preparation||{},j=p.job,r=p.result;
  const busy=p.research_pending||(j&&['pending','running'].includes(j.state)), ready=data.messages.some(m=>m.step===0);
  const hasSource=data.evidence.some(e=>e.current_for_review&&e.business_for_review!==false);
  const failed=!ready&&!busy&&(j?.state==='failed'||['needs_attention','needs_evidence'].includes(r?.state));
  const title=ready?'Your email is ready to review':busy?(p.research_pending?'Checking the enquiry journey':j?.state==='running'?'Preparing your email':'Email preparation is queued'):failed?'This prospect needs a closer look':!hasSource?'Start with the business research':!data.contacts.length?'Find a published business contact':'Create a relevant first email';
  const explanation=ready?'Research and the draft are saved. Review the wording below before any sending decision.':busy?(!researchRunning?'Research automation is OFF. Turn it on in Settings to process this email; nothing will be sent.':p.research_pending?'Checking the enquiry journey before writing. Nothing will be sent.':j?.state==='running'?'Checking the business, matching one offer and writing one personalized draft. Nothing will be sent.':'Your request is saved and waiting for the email preparation worker. No need to click again. Nothing will be sent.'):failed?'We could not safely finish preparation. Your saved research is preserved.':!hasSource?'Research the business and save the sources before choosing an offer.':!data.contacts.length?'A published contact is needed before a personalized email can be prepared.':'Use the saved research to match one useful offer and write one personalized email.';
  return `<section class="next-action ${ready?'is-ready':failed?'is-attention':''}" aria-label="Email preparation" data-preparation-active="${Boolean(busy)}"><div><span class="eyebrow">${ready?'READY FOR YOUR REVIEW':busy?'IN PROGRESS':'NEXT STEP'}</span><h3>${title}</h3><p>${explanation}</p>${failed?`<details><summary>What needs attention?</summary><p>${esc(j?.error||r?.reason||'Inspect current research before retrying.')}</p></details>`:''}${busy&&r?`<details><summary>Previous attempt: ${esc(r.state.replaceAll('_',' '))}</summary><p>${esc(r.reason)}</p></details>`:''}</div><div class="next-action-controls">${ready?'<a class="button primary" href="#email-sequence">Review email</a>':busy?'<span class="workspace-pill">Preparing…</span>':''}</div></section>`;
}
async function pollPreparation(id){
  if(currentId!==id||document.hidden||$('#pipeline').hidden)return;
  try{const p=await api(`/api/leads/${id}/preparation`);if(currentId!==id)return;
    if(p.research_pending){
      const panel=document.querySelector('[aria-label="Email preparation"]');
      if(panel){panel.hidden=false;panel.dataset.preparationActive='true';panel.querySelector('h3').textContent=researchRunning?'Checking the enquiry journey':'Journey audit is queued';panel.querySelector('p').textContent='Checking public enquiry links, form labels and mobile layout before writing. Nothing will be sent.';}
      const button=$('#prepare-emails');if(button){button.disabled=true;button.textContent='Checking enquiry journey…';}
    }
    if(!p.research_pending && p.job && ['pending','running'].includes(p.job.state)){
      const panel=document.querySelector('[aria-label="Email preparation"]');
      if(panel){panel.hidden=false;panel.dataset.preparationActive='true';panel.querySelector('h3').textContent=p.job.state==='running'?'Preparing your email':'Email preparation is queued';panel.querySelector('p').textContent=!researchRunning?'Research automation is OFF. Turn it on in Settings to continue.':p.job.state==='running'?'Checking the business, matching one offer and writing one personalized draft. Nothing will be sent.':'Your request is saved and waiting for the email preparation worker. No need to click again. Nothing will be sent.';}
    }
    if(p.research_pending||(p.job&&['pending','running'].includes(p.job.state))){preparationTimer=setTimeout(()=>pollPreparation(id),4000);return;}
    if(detailDirty){notice('Preparation finished. Your edits are preserved; use Refresh to view the result.');return;}
    await loadLead(id);
    if(p.result?.state==='drafts_ready')$('#email-sequence')?.scrollIntoView({block:'start'});
  }catch(e){notice('Preparation status unavailable: '+e.message,true);}
}
async function pollResearchActivity(id, previous, refreshNeeded=false){
  if(currentId!==id)return;
  if(document.hidden||$('#pipeline').hidden){researchActivityTimer=setTimeout(()=>pollResearchActivity(id,previous,refreshNeeded),5000);return;}
  const turn=researchActivityRequest;
  try{
    const activity=await api(`/api/leads/${id}/activity`,'GET',undefined,{feedback:false});
    if(currentId!==id||turn!==researchActivityRequest)return;
    const changed=JSON.stringify(previous)!==JSON.stringify(activity);
    const finished=previous.active_jobs.length>0&&activity.active_jobs.length===0;
    if(finished&&!detailDirty&&!document.querySelector('#detail details[open],#detail [data-edit]')){
      await refresh({reloadDetail:false,includeDiagnostics:false});
      if(currentId===id&&turn===researchActivityRequest)await loadLead(id);
      return;
    }
    refreshNeeded=refreshNeeded||finished;
    if(changed||finished){
      window.WorkbenchWorkspace.updateResearchActivity(activity,{esc,reload:()=>loadLead(id),refreshNeeded});
      const lead=allLeads.find(l=>l.id===id);if(lead){lead.source_job=activity.job;lead.status=activity.lead_status;renderLeads();}
    }
    $('#prospect-research-status')?.querySelector('[data-status-unavailable]')?.remove();
    researchActivityTimer=setTimeout(()=>pollResearchActivity(id,activity,refreshNeeded),5000);
  }catch{
    if(currentId!==id||turn!==researchActivityRequest)return;
    const panel=$('#prospect-research-status');
    if(panel&&!panel.querySelector('[data-status-unavailable]')){const p=document.createElement('p');p.dataset.statusUnavailable='';p.className='error';p.setAttribute('role','status');p.textContent='Live status is unavailable. Displayed results may be outdated; queued work may still run. Reconnecting automatically.';panel.append(p);}
    researchActivityTimer=setTimeout(()=>pollResearchActivity(id,previous,refreshNeeded),15000);
  }
}
async function loadLead(id){
  clearTimeout(preparationTimer);
  clearTimeout(researchActivityTimer);researchActivityRequest++;
  currentId=id;const request=++detailRequest;renderLeads();const data=await api(`/api/leads/${id}`);if(request!==detailRequest||currentId!==id)return;const l=data.lead;const address=new URL(location.href);address.searchParams.set('prospect',String(id));history.replaceState(null,'',address.pathname+address.search+address.hash);
  if(l.deleted_at){$('#detail').innerHTML=`<section class="panel"><span class="badge">Deleted prospect</span><h2>${esc(l.company)}</h2><p>Deleted ${stamp(l.deleted_at)} · ${esc(l.delete_reason)}</p><p>Pending emails are cancelled. History and suppression are preserved. Restore from Campaigns → Deleted prospects before reviewing further outreach.</p><button id="deleted-campaigns">Open campaigns</button>${data.messages.map(m=>`<details><summary>${esc(m.subject)} · ${esc(m.state)}</summary><pre>${esc(m.body)}</pre></details>`).join('')}</section>`;$('#deleted-campaigns').onclick=()=>view('campaigns');return;}
  let finding=JSON.parse(l.findings||"[]")[0]||{};
  if(!l.service&&finding.review_required===true&&finding.proposal_method==='explicit_public_signal')finding=data.offer_proposals.find(p=>p.service===finding.service)||data.offer_proposals[0]||{};
  const isProfile=l.lead_kind==='profile';
  const profileReview=JSON.parse(l.profile_review||"{}");
  const reviewEvidence=data.evidence.filter(e=>e.current_for_review&&e.business_for_review!==false);
  const triggerEvidence=data.evidence.filter(e=>e.current_for_review&&(e.business_for_review!==false||e.social_for_review));
  const crawlReport=data.crawl?JSON.parse(data.crawl.report):{};
  const cp=crawlReport.checkpoint||{},now=Date.now()/1000;
  const pendingRetry=[...(cp.retry_urls||[]),...(cp.retry_sitemaps||[])],hasQueued=!!(cp.frontier?.length||cp.sitemap_queue?.length||cp.inflight||cp.sitemap_inflight);
  const retryAt=Math.max(cp.domain_not_before||0,hasQueued?0:Math.min(...pendingRetry.map(r=>r.not_before||0)));
  const canContinue=!!(hasQueued||pendingRetry.length)&&retryAt<=now;
  $("#detail").innerHTML=`<div class="lead-heading"><span class="eyebrow">CAMPAIGN ${esc(l.campaign)} · ${esc(l.status)}${String(finding.qualification_method||'').startsWith('research_ai')?' · AI prepared; message review pending':''}</span><h2>${esc(l.company)}</h2>${isProfile?`<p><strong>Profile prospect · ${esc(l.website_status.replaceAll("_"," "))}</strong></p>${link(l.profile_url)}<p>Website not found means no match in our search, not confirmed absence. Review the search report and the business's current inquiry/order process.</p>`:link(l.website)}<p class="small">Discovery source: ${link(l.source_url)}</p><p>${esc(l.research_notes)}</p>${pendingRetry.length?`<p class="small">${pendingRetry.length} pages awaiting a bounded retry.</p>`:""}${retryAt>now&&Number.isFinite(retryAt)?`<p class="small">Continue available after ${esc(new Date(retryAt*1000).toLocaleString())}.</p>`:""}<div class="actions"><button id="prepare-emails" type="button" class="primary" ${data.preparation?.job&&['pending','running'].includes(data.preparation.job.state)?'disabled':''}>Prepare emails</button><button id="research-again">Research again</button><button id="continue-research" ${isProfile||!canContinue?"disabled":""}>Continue crawl</button><button id="contact-research" ${isProfile||!reviewEvidence.length?"disabled":""}>Find public contacts</button><button id="check-verifier">Check verifier</button><button id="screenshot" ${isProfile?"disabled":""}>Desktop & mobile audit</button><button id="performance" ${isProfile?"disabled":""}>PageSpeed audit</button></div></div>
    ${priorityHTML(data.priority)}
    ${!isProfile?professionalHTML(data,reviewEvidence):''}
    ${socialPostsHTML(data.social_captures||[],reviewEvidence.length>0)}
    ${data.events.filter(e=>e.kind==='contact_research').slice(0,1).map(e=>{const r=JSON.parse(e.detail);return `<details><summary>Public contact research · ${esc(r.state)} · ${Number(r.pages_saved||0)} captured pages</summary><p>${esc(r.note)}</p><pre>${esc(JSON.stringify(r,null,2))}</pre></details>`;}).join('')}
    ${data.events.filter(e=>e.kind==='performance').slice(0,1).map(e=>`<details><summary>Latest PageSpeed lab report</summary><p>Lab measurements vary. These do not establish conversion losses or actual visitor experience.</p><pre>${esc(e.detail)}</pre></details>`).join('')}
    ${data.crawl?`<details><summary>${isProfile?"Profile & website search report":"Crawl coverage & rendering report"}</summary><pre>${esc(JSON.stringify(JSON.parse(data.crawl.report),null,2))}</pre></details>`:''}
    ${data.events.filter(e=>e.kind==='prospect_signal').map(e=>{const s=JSON.parse(e.detail);const post=s.public_snapshot?.capture_method==='official_public_oembed'&&s.public_snapshot.state==='captured';return `<details><summary>${post?'Public X post':'Platform research'} · ${esc(s.platform)} · ${esc(s.state.replaceAll('_',' '))}</summary><p>${link(s.source_url)} · ${stamp(s.observed_at)}</p>${post?`<p>Single public post captured through X's publishing service. Posted date shown by X: ${esc(s.public_snapshot.posted_label||'unknown')}. This does not capture the author's profile or verify business identity, contact ownership or mailbox existence.</p><p>${esc(s.public_snapshot.text||'')}</p>`:''}<p>${esc(s.indexed_snippet||'')}</p><p>Indexed information can be stale. This match does not confirm company identity, buyer relevance or contact ownership. Platform email candidates require current official-source corroboration.</p>${s.community_profile_hint?communityProfileHTML(s.community_profile_hint):''}${s.person_recovery?personRecoveryHTML(s):''}<pre>${esc(JSON.stringify(s,null,2))}</pre></details>`;}).join('')}
    ${data.events.filter(e=>e.kind==='browser_business_reference').map(e=>{const s=JSON.parse(e.detail);return `<details><summary>Browser-observed business reference · review required</summary><p>${link(s.source_url)} · ${stamp(s.observed_at)}</p><p>${esc(s.observation)}</p><p>Website candidate: ${link(s.website_candidate)}</p><p>Saved from ${s.method==='browser_connector_reference'?'a browser connector export':'an operator observation'}. The server did not fetch this profile; this is not contact publication or identity proof. Review the separately captured company evidence.</p></details>`;}).join('')}
    ${preparationHTML(data,finding)}<div class="step-label">01 · Check original evidence</div>${data.evidence.map(e=>`<details data-evidence-id="${e.id}"><summary>#${e.id} · ${esc(e.title)}${e.current_for_review?"":" · Historical capture"}</summary><p>${link(e.url)} · ${stamp(e.fetched_at)}</p>${e.current_for_review?"":"<p>This page was not refreshed in the latest research attempt. It remains available as history; research it again before using it for new qualification.</p>"}<div class="evidence-text" data-source-text="${e.id}"></div></details>`).join("")||'<p>Research has not returned evidence yet. Check Operations.</p>'}
    <section class="panel offer-review" aria-label="Second workflow: select an offer"><h3>2 · Match one useful offer</h3><p>${esc(data.offer_workflow.note)}</p><div class="offer-node-list">${data.offer_workflow.nodes.map(n=>`<div><strong>${esc(n.label)}</strong><small>${esc(n.state.replaceAll('_',' '))}</small></div>`).join('')}</div><p>${data.offer_workflow.recommended_artifacts.length?'Suggested proof of value: '+esc(data.offer_workflow.recommended_artifacts.join(', ').replaceAll('_',' ')):'Qualify this prospect before treating an offer as selected.'}</p></section>
    <details><summary>02 · Advanced: edit qualification & offer manually</summary>
      <p>Confirm the business is real, in scope, and that the observation is supported. Suggestions describe opportunities, not guaranteed outcomes.</p>
      <div id="offer-proposals">${data.offer_proposals.length?'<p>Compare sourced possibilities. Selecting one fills its quote and suggestion; review them before saving.</p>'+data.offer_proposals.map((f,i)=>`<button type="button" data-offer-proposal="${i}">${esc(f.service.replaceAll('_',' '))} · use this sourced idea</button>`).join(''):'<p>No explicit public signal produced a suggestion. Review a current source before choosing an offer.</p>'}</div>
      ${reviewEvidence.length?"":"<p>No source pages were refreshed in the latest research. Research again before qualifying this company.</p>"}<form id="review-form"><label>Company name<input name="company" value="${esc(l.company)}" required></label>
      <div class="columns"><label>Confirmed country<select name="country">${options(["UK","US"],l.country)}</select></label><label>Prospect timezone<select name="timezone">${options(["Europe/London","America/New_York","America/Chicago","America/Denver","America/Los_Angeles","America/Phoenix","America/Anchorage","Pacific/Honolulu"],l.timezone)}</select></label></div>
      <label>Country evidence: saved business source<select name="country_source">${reviewEvidence.map(e=>`<option value="${esc(e.url)}" ${e.url===l.country_source?'selected':''}>${esc(e.url)}</option>`).join("")}</select></label>
      <label>Exact country/location quote<textarea name="country_quote" minlength="3" maxlength="700" required>${esc(finding.country_quote||"")}</textarea></label>
      <div class="columns"><label>Business type<select name="business_type">${options(["corporate","sole_trader","other"],l.business_type)}</select></label><label>Primary service<select name="service">${options(isProfile?(l.campaign==='A'?["website_build","chatbot","ai_calling_agent"]:["store_launch","chatbot"]):(l.campaign==='A'?["website_build","website_improvement","chatbot","ai_calling_agent"]:["store_launch","store_improvement","chatbot","whatsapp_marketing","whatsapp_automation"]),l.service||finding.service)}</select></label></div>
      ${isProfile?`<fieldset><legend>Review profile-only business</legend><label>Why this profile belongs to the business<textarea name="profile_ownership_notes" required minlength="30">${esc(profileReview.ownership_notes||"")}</textarea></label><label>Exact quote showing business activity or services<textarea name="profile_activity_quote" required minlength="8">${esc(profileReview.activity_quote||"")}</textarea></label><label>Website-search scope and remaining uncertainty<textarea name="website_search_notes" required minlength="30">${esc(profileReview.website_search_notes||"")}</textarea></label><label class="check"><input name="website_search_reviewed" type="checkbox" required>I reviewed the search results, business/profile identity and activity. Website absence is not confirmed.</label></fieldset>`:""}
      <label>Reviewed primary goal<select name="primary_goal">${options(l.campaign==='A'?['inquiries_bookings']:['d2c_growth'],finding.offer_context?.primary_goal)}</select></label>
      ${l.campaign==='B'?`<fieldset><legend>Confirm the D2C business and selling process</legend><label>Selling stage<select name="selling_stage">${options(['unknown','starting_ecommerce','selling_online','not_d2c'],finding.offer_context?.selling_stage||'unknown')}</select></label><label>Business model source<select name="commerce_evidence_id">${reviewEvidence.map(e=>`<option value="${e.id}" ${e.id===finding.offer_context?.commerce_evidence_id?'selected':''}>#${e.id} ${esc(e.title)}</option>`).join('')}</select></label><label>Exact quote supporting product ownership / selling or launch process<textarea name="commerce_quote" minlength="8" maxlength="700" required>${esc(finding.offer_context?.commerce_quote||'')}</textarea></label><label>Why this is a relevant D2C business<textarea name="d2c_fit_notes" minlength="20" maxlength="1500" required>${esc(finding.offer_context?.d2c_fit_notes||'')}</textarea></label></fieldset>`:''}
      <fieldset id="whatsapp-review"><legend>WhatsApp fit and permission</legend><p>A public WhatsApp link does not establish customer permission. Unknown means qualification planning only.</p><label>Customer channel fit<select name="channel_fit_status">${options(['unknown','confirmed','not_suitable'],finding.offer_context?.channel_fit_status||'unknown')}</select></label><label>Customer permission setup<select name="customer_permission_status">${options(['unknown','confirmed','not_suitable'],finding.offer_context?.customer_permission_status||'unknown')}</select></label></fieldset>
      <label>Why this business fits<input name="fit_notes" minlength="12" value="${esc(l.fit_notes)}" required></label>
      <label>Industry, if established<input name="industry" maxlength="150" value="${esc(finding.industry||"")}"></label>
      <label>WhatsApp channel fit and unknowns (required for WhatsApp offers)<textarea name="channel_fit_notes" maxlength="1500" placeholder="Record the public channel signal and customer permission/workflow questions still to ask.">${esc(finding.channel_fit_notes||"")}</textarea></label>
      <label>Evidence page<select name="evidence_id">${reviewEvidence.map(e=>`<option value="${e.id}" ${e.id===finding.evidence_id?'selected':''}>#${e.id} ${esc(e.title)}</option>`).join("")}</select></label>
      <label>Exact quote from saved page<textarea name="quote" minlength="8" maxlength="700" required>${esc(finding.quote||"")}</textarea></label>
      <label>Specific observation for the email<textarea name="observation" minlength="12" required>${esc(finding.kind==='needs_review'?'':finding.observation||"")}</textarea></label>
      <label>One relevant suggestion<textarea name="suggestion" minlength="12" required>${esc(finding.suggestion||"")}</textarea></label>
      <details><summary>Recent announcement, if available</summary><p>No announcement is required when a useful website observation is available. Confirm the event and its recency before mentioning it.</p>
      <label>Trigger description for the email<textarea name="recent_trigger" maxlength="700">${esc(finding.trigger?.description||"")}</textarea></label>
      <label>Announcement source<select name="trigger_evidence_id"><option value="">None</option>${triggerEvidence.map(e=>`<option value="${e.id}" ${e.id===finding.trigger?.evidence_id?'selected':''}>#${e.id} ${esc(e.title)}</option>`).join("")}</select></label>
      <label>Exact source quote<textarea name="trigger_quote" maxlength="700">${esc(finding.trigger?.quote||"")}</textarea></label></details>
      <details><summary>Extra source-backed follow-up idea, optional</summary><p>Without this, the second touch adds a service-specific pilot or measurement suggestion.</p>
      <label>New suggestion<textarea name="followup_suggestion" maxlength="1200">${esc(finding.followup?.suggestion||"")}</textarea></label>
      <label>Source page<select name="followup_evidence_id"><option value="">None</option>${reviewEvidence.map(e=>`<option value="${e.id}" ${e.id===finding.followup?.evidence_id?'selected':''}>#${e.id} ${esc(e.title)}</option>`).join("")}</select></label>
      <label>Exact source quote<textarea name="followup_quote" maxlength="700">${esc(finding.followup?.quote||"")}</textarea></label></details>
      <button class="primary" type="submit">Save qualification</button></form>
    </details>
    <div id="email-sequence" class="step-label" style="scroll-margin-top:130px">03 · Contact, verification & email sequence</div>
    <p class="small">${esc(data.email_writer?.note||"AI writer configuration unavailable.")}</p>
    ${(data.review_candidates||[]).length?`<details><summary>Published inboxes requiring ownership review (${data.review_candidates.length})</summary><p>These addresses were published on saved business pages or profiles and require ownership review. They may belong to the business, a supplier or someone else. No contact or verification was created automatically.</p>${data.review_candidates.map(c=>`<div class="item"><strong>${esc(c.email)}</strong><p>${link(c.source_url)}<br>${esc(c.reason)}</p></div>`).join('')}</details>`:''}
    ${data.contacts.map(c=>contactHTML(c,data.messages.filter(m=>m.contact_id===c.id),data.email_writer)).join("")||'<p>No reviewed business contact yet. Review published candidates or add a sourced business contact below. Addresses are never guessed.</p>'}
    <details><summary>Add a sourced contact</summary><p>Use an address published on a saved official business page. Without current publication proof it stays held; use Find public contacts to refresh the source.</p><form id="contact-form"><label>Business email<input name="email" type="email" required></label><label>Source URL<input name="source_url" type="url" required></label><div class="columns"><label>Name<input name="name"></label><label>Role<input name="role"></label></div><label>Company ownership evidence, for another-domain inbox<textarea name="ownership_notes" maxlength="2000" placeholder="Explain why the published address belongs to this business, rather than a supplier. At least 30 characters for another-domain addresses."></textarea></label><button type="submit">Save contact</button></form></details>
    <details><summary>Conversation activity</summary>${data.events.map(e=>`<div class="item"><strong>${esc(e.kind)}</strong> · ${stamp(e.created_at)}<pre>${esc(e.detail)}</pre></div>`).join("")||'<p>No activity yet.</p>'}</details>${salesHTML(data)}${growthHTML(data)}`;
  window.WorkbenchWorkspace.organize(data,finding,{esc,link,api,reload:()=>loadLead(id)});
  document.querySelectorAll('[data-source-text]').forEach(node=>node.closest('details').addEventListener('toggle',()=>{if(node.closest('details').open&&!node.dataset.loaded){node.textContent=data.evidence.find(e=>e.id===Number(node.dataset.sourceText))?.text||'';node.dataset.loaded='true';}}));
  detailDirty=false;$('#detail').oninput=()=>{detailDirty=true;};
  if(data.research_activity)researchActivityTimer=setTimeout(()=>pollResearchActivity(id,data.research_activity),5000);
  if(data.preparation?.research_pending||(data.preparation?.job&&['pending','running'].includes(data.preparation.job.state)))preparationTimer=setTimeout(()=>pollPreparation(id),4000);
  $('#prepare-emails').onclick=()=>act(()=>api(`/api/leads/${id}/prepare`,'POST'),'Preparation queued. One email will be created; nothing will be sent.');
  document.querySelectorAll('[data-single-email]').forEach(b=>b.onclick=()=>act(()=>api(`/api/contacts/${b.dataset.singleEmail}/single-email`,'POST'),'Initial email kept. Old follow-ups archived; nothing sent.'));
  bindSales(id,data);
  bindGrowth(id,data);
  $("#research-again").onclick=()=>act(()=>api(`/api/leads/${id}/research`,"POST"),"Research queued.");
  $("#continue-research").onclick=()=>act(()=>api(`/api/leads/${id}/continue-research`,"POST"),"Next crawl batch queued; saved evidence is preserved.");
  $("#contact-research").onclick=()=>act(()=>api(`/api/leads/${id}/contact-research`,"POST"),"Official contact/team source research queued; indexed emails stay unverified.");
  if($('#professional-research-form'))$('#professional-research-form').onsubmit=e=>{e.preventDefault();act(()=>api(`/api/leads/${id}/professional-research`,'POST',formObject(e.target)),'Public professional-profile research queued. Published emails remain candidates.');};
  document.querySelectorAll('[data-professional-review]').forEach(f=>f.onsubmit=e=>{e.preventDefault();const obj=formObject(f);obj.capture_id=Number(f.dataset.professionalReview);obj.company_evidence_id=Number(obj.company_evidence_id);obj.reviewed_current_employer_and_publication=!!f.elements.reviewed_current_employer_and_publication.checked;act(()=>api(`/api/leads/${id}/professional-review`,'POST',obj),'Reviewed professional contact imported; technical verification queued. Sending remains controlled separately.');});
  $("#check-verifier").onclick=async()=>{notice("Checking verifier…");try{const result=await api("/api/providers/reacher");notice(result.reason,!result.ready);}catch(error){notice(error.message,true);}};
  $("#screenshot").onclick=()=>act(()=>api(`/api/leads/${id}/screenshot`,"POST"),"Screenshots queued; desktop/mobile links will appear in this prospect's research status.");
  $("#performance").onclick=()=>act(()=>api(`/api/leads/${id}/performance`,"POST"),"PageSpeed audit queued; provider quota/key may be required. Refresh after the job finishes.");
  const reviewForm=$("#review-form");
  const updateChannelReview=()=>{const needed=reviewForm.elements.service.value.startsWith('whatsapp_');$('#whatsapp-review').hidden=!needed;reviewForm.elements.channel_fit_notes.required=needed;reviewForm.elements.channel_fit_notes.minLength=needed?20:0;};
  reviewForm.elements.service.onchange=updateChannelReview;updateChannelReview();
  document.querySelectorAll('[data-offer-proposal]').forEach(button=>button.onclick=()=>{const proposal=data.offer_proposals[Number(button.dataset.offerProposal)];for(const key of ['service','evidence_id','quote','observation','suggestion'])reviewForm.elements[key].value=proposal[key];updateChannelReview();notice('Sourced idea selected. Review country, business fit, quote and suggestion before saving.');});
  $("#review-form").onsubmit=e=>{e.preventDefault();const obj=formObject(e.target);if(isProfile)obj.website_search_reviewed=!!e.target.elements.website_search_reviewed.checked;obj.evidence_id=Number(obj.evidence_id);for(const key of ["trigger_evidence_id","followup_evidence_id","commerce_evidence_id"])obj[key]=obj[key]?Number(obj[key]):null;act(()=>api(`/api/leads/${id}/review`,"POST",obj),"Company qualified. Generate drafts for your chosen contact.");};
  $("#contact-form").onsubmit=e=>{e.preventDefault();act(()=>api(`/api/leads/${id}/contacts`,"POST",formObject(e.target)),"Contact saved. Check its source status and verification.");};
  document.querySelectorAll("[data-verify]").forEach(b=>b.onclick=()=>act(()=>api(`/api/contacts/${b.dataset.verify}/verify`,"POST"),"Verification queued."));
  document.querySelectorAll("[data-draft]").forEach(b=>b.onclick=()=>act(()=>api(`/api/contacts/${b.dataset.draft}/draft`,"POST"),"Personalized email created. Review the email and its sources."));
  if($('#social-research-button'))$('#social-research-button').onclick=()=>act(()=>api(`/api/leads/${currentId}/social-research`,'POST'),'Post research queued. Sending controls are unchanged.');
  document.querySelectorAll("[data-suppress]").forEach(b=>b.onclick=()=>act(()=>api(`/api/contacts/${b.dataset.suppress}/suppress`,"POST",{reason:"Operator marked do not contact"}),"Contact suppressed."));
  document.querySelectorAll("[data-profile]").forEach(f=>f.onsubmit=e=>{e.preventDefault();act(()=>api(`/api/contacts/${f.dataset.profile}/profile`,"PUT",formObject(f)),"Contact updated. Regenerate drafts to update greeting.");});
  document.querySelectorAll("[data-edit]").forEach(f=>f.onsubmit=e=>{e.preventDefault();act(()=>api(`/api/messages/${f.dataset.edit}`,"PUT",formObject(f)),"Draft saved.");});
  document.querySelectorAll("[data-approve]").forEach(f=>f.onsubmit=e=>{e.preventDefault();const obj=formObject(f);obj.reviewed_all_messages=true;act(()=>api(`/api/contacts/${f.dataset.approve}/approve`,"POST",obj),"Sequence approved. Global sending controls still apply.");});
  document.querySelectorAll("[data-reconcile]").forEach(f=>f.onsubmit=e=>{e.preventDefault();act(()=>api(`/api/messages/${f.dataset.reconcile}/reconcile`,"POST",formObject(f)),"Result recorded; contact remains held for review.");});
  document.querySelectorAll("[data-resume-contact]").forEach(f=>f.onsubmit=e=>{e.preventDefault();const obj=formObject(f);obj.next_at=new Date(obj.next_at).getTime()/1000;obj.reviewed_remaining_messages=true;act(()=>api(`/api/contacts/${f.dataset.resumeContact}/resume`,"POST",obj),"Contact resumed at the reviewed time.");});
  document.querySelectorAll('[data-revise-sequence]').forEach(f=>f.onsubmit=e=>{e.preventDefault();act(()=>api(`/api/contacts/${f.dataset.reviseSequence}/revise`,'POST',{...formObject(f),reviewed_pending_messages:true}),'Approval revoked. Review the evidence and email before approving again.');});
}
function communityInboxHTML(hint){
  const routes=hint.candidate_routes||[];
  return routes.length?`<ul>${routes.map(r=>`<li>${esc(r.email)} · Inbox purpose: ${esc(r.purpose.replaceAll('_',' '))} · Buyer contact not verified</li>`).join('')}</ul>`:'<p class="small">Buyer-contact context not established.</p>';
}
function communityProfileHTML(h){
  return `<section class="panel"><strong>${esc(h.name||'Community profile unavailable')}</strong><p>${link(h.profile_url)} · ${esc(h.state.replaceAll('_',' '))}${h.cached?' · Cached response':''} · Third-party hint</p><p class="small">${link(h.transport_url)} · Retrieved ${stamp(h.retrieved_at)}</p>${h.published_website_hint?`<p class="small">Profile website reference: ${link(h.published_website_hint)} · Ownership needs review</p>`:''}<div class="evidence-text">${esc(h.description||'')}</div><p>${h.published_email_candidates?.length?esc(h.published_email_candidates.join(', ')):'No email candidate returned.'}</p>${communityInboxHTML(h)}</section>`;
}
function personRecoveryHTML(signal){
  const people=signal.person_recovery?.matched_people||[];
  const company=signal.person_recovery?.company_search?.company_candidate;
  const observations=(signal.person_recovery?.official_person_observations||[]).filter(p=>!p.matches_requested_profile);
  const companyHTML=company?`<section class="panel company-only-recovery"><strong>Company source found · person identity pending</strong><p>${esc(company.company)} · ${link(company.website)}</p><p class="small">The current company homepage matched its own name. This does not verify the indexed person, buyer role or personal email.</p></section>`:'';
  const observationHTML=observations.length?`<h4>Company-page observations · identity unresolved</h4>${observations.map(p=>`<section class="panel"><strong>${esc(p.name)}</strong> · ${esc(p.role)}<p>${esc(p.quote)}</p><p>${link(p.source_url)} · ${stamp(p.observed_at)}</p><p class="small">Exact requested profile link is missing. This record does not approve a person or recipient.</p></section>`).join('')}`:'';
  return `<section class="linkedin-person-recovery"><h4>LinkedIn-linked person recovery</h4><p>Native profile access: ${esc(signal.public_snapshot?.state||'unknown')}. ${people.length} matching company-page records. LinkedIn access was not recovered.</p>${companyHTML}${observationHTML}${people.map(p=>`<section class="panel"><strong>${esc(p.name)}</strong> · ${esc(p.role)}<p>${esc(p.quote)}</p><p>Current publication source: ${link(p.source_url)} · ${stamp(p.observed_at)}</p><p>Published email candidates: ${p.email_publications?.length?esc(p.email_publications.map(v=>v.email).join(', ')):'None in this record'}</p><p class="small">Company identity, current employer, inbox ownership, buyer fit and mailbox validity need review.</p></section>`).join('')}</section>`;
}
function professionalDiscoveryHTML(report){
  if(!report)return '';
  const hints=report.other_public_profile_hints||[];
  const pages=report.official_link_refresh||[];
  const people=report.named_people||[];
  const mirrors=report.community_profile_hints||[];
  const mirrorHTML=mirrors.length?`<h4>Community X profile hints</h4><p class="small">Third-party FxEmbed data. Current X publication, buyer role and mailbox validity need verification; these hints cannot import contacts.</p>${mirrors.map(communityProfileHTML).join('')}`:'';
  const sources=[...new Set((report.queries||[]).flatMap(q=>(q.providers||[]).map(p=>p.provider)))];
  return `<section id="professional-discovery-sources"><h4>Discovery sources</h4><p class="small">${pages.filter(p=>p.state==='captured').length} current company pages refreshed · ${sources.length} search engine groups · URL index: ${esc(report.url_index?.state||'not used')} · ${hints.length} other public profile hints · ${people.length} named people</p><p class="small">Profile links guide further research. A linked or indexed profile does not verify an email, current employer or buyer role.</p>${people.length?`<h4>People observed on company pages</h4><ul>${people.map(p=>`<li><strong>${esc(p.name)}</strong> · ${esc(p.role||'Role not established')}<p class="small">${esc(p.quote||'')}<br>${link(p.source_url)} · Employer and buyer relevance need review</p>${p.email_publications?.length?`<p>Published in this company-page person record: ${esc(p.email_publications.map(v=>v.email).join(', '))}. Inbox ownership and mailbox validity need review.</p>`:''}<p class="small">${(p.professional_links||[]).map(link).join(' · ')}</p></li>`).join('')}</ul>`:''}${hints.length?`<ul>${hints.map(h=>`<li>${link(h.url)} <span class="badge">${h.origin==='current_official_navigation'?'Observed company link':'Indexed · identity needs review'}</span></li>`).join('')}</ul>`:''}${mirrorHTML}</section>`;
}
function renderSourceStatus(status){
  const target=$('#provider-source-status');if(!target)return;
  target.innerHTML=`<div class="source-coverage-scroll"><table><thead><tr><th>Provider</th><th>Configured</th><th>Last result</th><th>Captured sources</th><th>Sources with contacts</th></tr></thead><tbody>${status.providers.map(p=>`<tr><td>${esc(p.provider)}</td><td>${p.configured?'Yes':'No'}</td><td>${esc(p.last_state)}${p.observed_at?' · '+stamp(p.observed_at):''}</td><td>${Number(p.captured_sources)}</td><td>${Number(p.contact_sources)}</td></tr>`).join('')}</tbody></table></div><p class="small">${esc(status.note)}</p><details><summary>Latest operations and timing</summary>${status.observations.slice(0,20).map(o=>`<p>${esc(o.operation)} · ${esc(o.state)} · ${link(o.target.startsWith('http')?o.target:'')} ${o.elapsed_seconds===null?'':Number(o.elapsed_seconds)+'s'} · ${Number(o.published_contact_candidates)} contact candidates${o.partial?' · partial':''}${o.coverage==='bounded_visible_posts'?' · bounded post sample':''}</p>`).join('')||'<p>No saved operation results yet.</p>'}</details>`;
}

function socialPostsHTML(rows,canResearch){
  return `<details id="social-posts"><summary>LinkedIn / X post research · ${rows.reduce((n,r)=>n+(r.posts||[]).length,0)} posts</summary><button id="social-research-button" ${canResearch?"":"disabled"}>Research LinkedIn / X posts</button><p>Author-matched visible posts are background evidence. Review company ownership, the actual date and relevance before selecting a post as the recent-announcement source in business review. No contact is imported from a post automatically.</p>${rows.map(r=>`<section class="panel"><h4>${link(r.profile_url)}</h4><p>${esc(r.state)} · ${stamp(r.observed_at)}${r.fresh?'':' · stale'} · ${esc(r.stop_reason||'')}</p>${(r.posts||[]).map(p=>`<article><p>${link(p.url)} · ${p.published_at?esc(p.published_at):'Publication date not established'}</p><div class="evidence-text">${esc(p.text)}</div><p class="small">Saved ${stamp(p.observed_at)} · Review required</p></article>`).join('')}</section>`).join('')}</details>`;
}

function professionalHTML(data,businessEvidence){
  const rows=data.professional_captures||[];
  return `<details id="professional-sources"><summary>Public professional profiles · ${rows.length} latest observations</summary><p>Research public LinkedIn /in/ and X bios plus current company team pages. Staff-card emails show their company source; profile emails need a current capture. Optional Contact Info reads only fields visible to your signed-in account when enabled in Settings. Guessed addresses are excluded. Confirm the person's current company and buyer role using independent official-company evidence.</p><form id="professional-research-form"><label>Known public profile URL (blank = automatic search)<input name="profile_url" type="url" maxlength="2000" placeholder="https://www.linkedin.com/in/name"></label><button ${businessEvidence.length?'':'disabled'}>Research public professional profiles</button></form>${professionalDiscoveryHTML(data.professional_report)}${data.professional_report?`<details><summary>Last professional research · ${esc(data.professional_report.state)}</summary><p>${esc(data.professional_report.note)}</p><pre>${esc(JSON.stringify(data.professional_report,null,2))}</pre></details>`:""}${rows.map(s=>`<section class="panel"><h3>${esc(s.name||'Profile unavailable')}</h3><p>${link(s.url)} · ${stamp(s.observed_at)} · ${esc(s.state.replaceAll('_',' '))}${s.fresh?'':' · Stale'}</p><p>${esc(s.headline)}</p><p class="small">Scope: ${esc(s.scope)} · Sections: ${esc(Object.keys(s.sections||{}).join(", ")||"top card/About")}${s.section_errors?.length?" · Some optional sections unavailable":""}</p><div class="evidence-text">${esc(s.text)}</div><p>${s.published_emails.length?esc(s.published_emails.join(', ')):'No published email in this capture.'}</p>${s.reviewed_emails?.length?'<p>Current employer/source review passed for '+esc(s.reviewed_emails.join(', '))+'. Mailbox verification remains separate.</p>':''}${s.state==='captured'&&s.fresh&&s.published_emails.some(a=>!s.reviewed_emails?.includes(a))&&businessEvidence.length?`<form data-professional-review="${s.capture_id}"><label>Published business email<select name="email">${s.published_emails.filter(a=>!s.reviewed_emails?.includes(a)).map(a=>`<option>${esc(a)}</option>`).join('')}</select></label><label>Exact current-employer quote from this profile<textarea name="employer_quote" required minlength="8" maxlength="700"></textarea></label><label>Exact relevant buyer-role quote from this profile<textarea name="role_quote" required minlength="3" maxlength="700"></textarea></label><label>Independent official company page<select name="company_evidence_id">${businessEvidence.map(p=>`<option value="${p.id}">#${p.id} ${esc(p.title)}</option>`).join('')}</select></label><label>Exact company-page quote corroborating this named person<textarea name="company_quote" required minlength="8" maxlength="700"></textarea></label><label>Inbox ownership and current-employer review notes<textarea name="ownership_notes" required minlength="30" maxlength="2000"></textarea></label><label class="check"><input type="checkbox" name="reviewed_current_employer_and_publication" required>I checked the current employer, role, source and business inbox ownership.</label><button>Review & import published contact</button></form>`:''}</section>`).join('')}</details>`;
}
function contactHTML(c,messages,writer){
  const initial=messages.find(m=>m.step===0), extras=messages.filter(m=>m.step>0);
  let verificationDetail={};
  try{verificationDetail=JSON.parse(c.verification_raw||'{}');}catch(_){}
  const checkerUnavailable=verificationDetail.error==='VerificationUnavailable'||verificationDetail.provider_status?.ready===false;
  const verification=checkerUnavailable?'Mailbox checker unavailable':c.verification==='safe'?(c.verification_fresh===false?'Mailbox recheck needed':'Mailbox check passed'):c.verification==='invalid'?'Mailbox check failed':'Mailbox check pending';
  const renderMessage=m=>`<div class="message"><div class="composer-meta"><span>${m.state==='draft'?'UNSENT DRAFT':esc(m.state.toUpperCase())}</span><span>${m.sent_at?'SMTP accepted '+stamp(m.sent_at):m.due_at?'Scheduled '+stamp(m.due_at):'Not scheduled'}</span></div>${m.state==='draft'?`<form data-edit="${m.id}"><label>Subject<input name="subject" value="${esc(m.subject)}" required maxlength="150"></label><label>Email<textarea name="body" required>${esc(m.body)}</textarea></label><div class="composer-footer"><button class="primary" type="submit">Save draft</button><span>Saving never sends this email.</span></div></form>`:`<h3>${esc(m.subject)}</h3><pre>${esc(m.body)}</pre>`}${m.state==='uncertain'?`<form data-reconcile="${m.id}"><p class="error">Delivery is uncertain. Inspect provider logs first.</p><label>Confirmed outcome<select name="outcome"><option value="sent">Provider accepted the message</option><option value="not_sent">Provider confirms it was not sent</option></select></label><label>Evidence<textarea name="evidence" required minlength="20"></textarea></label><button>Record reconciliation</button></form>`:''}</div>`;
  return `<section class="contact" data-contact="${c.id}"><div class="recipient-bar"><div><span class="eyebrow">TO</span><strong>${esc(c.email)}</strong>${c.delivery_state?`<span class="badge">${esc(c.delivery_state)}</span>`:''}${c.name?`<small>${esc(c.name)}${c.role?' · '+esc(c.role):''}</small>`:''}</div><span class="workspace-pill ${!checkerUnavailable&&c.verification==='safe'&&c.verification_fresh!==false?'positive':''}">${verification}</span></div>
  ${initial?renderMessage(initial):'<div class="email-empty"><h3>Your draft will appear here</h3><p>Use Create email above to prepare it from the business research.</p></div>'}
  ${messages.length&&!c.ai_drafts?`<p class="error">${esc(c.ai_draft_issue || 'Draft provenance needs review before approval.')}</p>`:''}
  ${extras.length?`<details class="legacy-emails"><summary>${extras.length} previous follow-up drafts · not part of your initial email</summary><p>New drafting creates one initial email. Preserve the first email and archive these old drafts to use the new flow.</p>${c.status==='new'&&messages.every(m=>m.state==='draft'&&!m.due_at&&!m.sent_at)?`<button data-single-email="${c.id}" type="button">Keep initial email only</button>`:''}${extras.map(m=>`<div class="item"><strong>${esc(m.subject)}</strong><pre>${esc(m.body)}</pre><span class="small">${esc(m.state)}</span></div>`).join('')}</details>`:''}
  <details class="contact-tools"><summary>Recipient details & sending approval<span>Verification, identity and sending checks</span></summary><p>${c.source_eligible?'Publication and inbox ownership checks passed. Buyer relevance still needs review.':esc(c.source_issue||'Current publication needs review.')}</p><p class="small">Source: ${link(c.source_url)}<br>Mailbox checked: ${stamp(c.verified_at)}. Technical checks do not establish buyer authority or permission.</p><div class="actions"><button data-verify="${c.id}" ${c.source_eligible?'':'disabled'}>Check mailbox</button><button data-draft="${c.id}" ${writer?.configured&&c.source_eligible&&c.status==='new'?'':'disabled'}>${initial?'Regenerate email':'Create email for this contact'}</button><button data-suppress="${c.id}">Do not contact</button></div><p class="small">Rewriting replaces an unapproved draft, including saved edits. Save draft stores your current wording without regenerating it.</p><form data-profile="${c.id}"><div class="columns"><label>Name<input name="name" value="${esc(c.name)}"></label><label>Role<input name="role" value="${esc(c.role)}"></label></div><button>Save contact</button></form><details><summary>Technical verification response</summary><pre>${esc(c.verification_raw)}</pre></details>
  ${['active','hold'].includes(c.status)&&[1,4].includes(messages.length)&&messages.every(m=>!m.sent_at&&['draft','queued','cancelled'].includes(m.state))?`<form data-revise-sequence="${c.id}"><h4>Return unsubmitted email to review</h4><label>Reason<textarea name="note" required minlength="20"></textarea></label><label class="check"><input type="checkbox" required>I checked that no message was submitted and reviewed the contact history.</label><button>Return to draft review</button></form>`:''}
  ${c.status==='hold'?`<form data-resume-contact="${c.id}"><label>Reason outreach can resume<textarea name="note" required minlength="20"></textarea></label><label>Next send time<input type="datetime-local" name="next_at" required></label><label class="check"><input type="checkbox" name="reviewed_remaining_messages" required>I reviewed replies and delivery status.</label><button>Resume contact</button></form>`:''}
  ${c.status==='new'&&c.ai_drafts&&messages.length===(writer?.message_count||1)&&messages.every(m=>m.state==='draft')?`<form data-approve="${c.id}" class="sending-approval"><h4>Approve the initial email</h4><p>Approval and global sending controls are separate. Sender details and an opt-out route are added when sending.</p><label>Outreach eligibility basis<textarea name="eligibility_basis" required minlength="20" placeholder="Record applicable business eligibility, sourcing and opt-out checks."></textarea></label><label>Why this recipient is relevant<textarea name="contact_relevance" required minlength="12"></textarea></label><label class="check"><input type="checkbox" name="reviewed_all_messages" required>I reviewed the source, recipient and email claims.</label><button class="primary">Approve email</button></form>`:''}</details></section>`;
}
async function schedules(){try{const rows=await api("/api/schedules");$("#schedules").innerHTML=rows.map(s=>`<div class="item"><strong>${esc(s.query)}</strong> · ${esc(s.campaign)} / ${esc(s.country_hint)}<p>Every ${s.interval_hours} hours · ${s.discovery_source==='google_maps'?'Campaign 3 · Google Business Profiles':s.profile_first?'business profiles first':'websites and profiles'} · next ${stamp(s.next_run)} · ${s.enabled?'enabled':'disabled'}</p>${s.enabled?`<button data-disable="${s.id}">Disable</button>`:''}</div>`).join("")||'<p>No recurring searches configured.</p>';document.querySelectorAll("[data-disable]").forEach(b=>b.onclick=()=>act(()=>api(`/api/schedules/${b.dataset.disable}`,"DELETE"),"Schedule disabled.").then(schedules));}catch(e){notice(e.message,true);}}
async function operations(){try{const [status,jobs,events,salesReport,delivery]=await Promise.all([api("/api/status"),api("/api/jobs"),api("/api/events"),api("/api/sales/report"),api('/api/delivery')]);const summary={stages:salesReport.stages,recorded_contract_value:salesReport.recorded_contract_value,open_tasks:salesReport.open_tasks,overdue_tasks:salesReport.overdue_tasks,note:salesReport.note};$("#health").innerHTML=`<h3>Deployment readiness</h3><p>Worker heartbeat: ${stamp(status.worker_heartbeat)}<br>Inbox current: ${status.imap_caught_up?'yes':'no'} · ${esc(status.imap_error)}<br>Search: ${esc(status.search_provider)} · AI suggestions: ${status.ai_enabled?'on':'off'} · Browser: ${status.browser_enabled?'on':'off'}</p><p>${status.sending_gaps.length?'Sending configuration still needs: '+esc(status.sending_gaps.join(', ')):'Sender configuration is present. Live provider checks are still necessary.'}</p><pre>${esc(JSON.stringify(status.funnel,null,2))}</pre><h3>Sales and next actions</h3><pre>${esc(JSON.stringify(summary,null,2))}</pre>`;
  $('#delivery-status').innerHTML=`<h3>Email delivery</h3><p>${['SENT','BOUNCED','REPLIED','UNSUBSCRIBED'].map(s=>`${s}: ${Number(delivery.states.find(r=>r.state===s)?.count||0)}`).join(' · ')}</p><p>Mailbox: ${esc(delivery.mailbox||'Not configured')} · Last 24 hours: ${Number(delivery.used_24h)}/${Number(delivery.daily_limit)} · Last hour: ${Number(delivery.used_1h)}/${Number(delivery.hourly_limit)}</p><p class="small">${esc(delivery.note)}</p><details><summary>Sending queue &amp; attempts</summary>${delivery.queue.map(m=>`<p>#${Number(m.id)} · ${esc(m.email)} · ${esc(m.state)} · ${Number(m.attempts)} attempts · ${m.due_at?stamp(m.due_at):'Not scheduled'}<br>${esc(m.error)}</p>`).join('')||'<p>No pending or failed messages.</p>'}<p class="small">Latest 50 queue entries. Uncertain messages are never retried automatically.</p><pre>${esc(JSON.stringify(delivery.attempts,null,2))}</pre></details><details><summary>Suppression list · ${Number(delivery.suppressed_count)}</summary>${delivery.suppression.map(r=>`<p>${esc(r.email)} · ${esc(r.reason)} · ${stamp(r.created_at)}</p>`).join('')||'<p>No suppressed addresses.</p>'}<p class="small">Latest 50 entries. Opt-outs, hard bounces and do-not-contact requests stay blocked after re-import.</p><form id="suppress-address"><label>Email address<input name="email" type="email" required maxlength="254"></label><label>Reason<input name="reason" required minlength="3" maxlength="500" placeholder="Requested no further contact"></label><button>Do not contact</button><p role="status" id="suppress-address-result"></p></form></details>`;
  $('#suppress-address').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('button');button.disabled=true;try{await api('/api/suppression','POST',Object.fromEntries(new FormData(form)));await operations();}catch(error){$('#suppress-address-result').textContent=error.message;}finally{button.disabled=false;}};
  $("#jobs").innerHTML=jobs.map(j=>`<div class="item"><strong>#${j.id} ${esc(j.kind)}</strong> · ${esc(j.state)} · attempts ${j.attempts}<p class="small">${esc(j.payload)} ${esc(j.error)}</p>${j.state==='failed'?`<button data-retry="${j.id}">Retry</button>`:''}</div>`).join("")||'<p>No jobs yet.</p>';
  $("#events").innerHTML=events.map(e=>{let extra='';if(e.kind==='screenshot'){const d=JSON.parse(e.detail);extra=Object.entries(d.files||(d.file?{mobile:d.file}:{})).map(([label,file])=>`<a href="/api/screenshots/${encodeURIComponent(file)}" target="_blank">View ${esc(label)} screenshot</a>`).join(' · ');}return `<div class="item"><strong>${esc(e.kind)}</strong> · ${stamp(e.created_at)}<pre>${esc(e.detail)}</pre>${extra}</div>`;}).join("")||'<p>No activity yet.</p>';
  document.querySelectorAll("[data-retry]").forEach(b=>b.onclick=()=>act(()=>api(`/api/jobs/${b.dataset.retry}/retry`,"POST"),"Job queued.").then(operations));
}catch(e){notice(e.message,true);}}
window.WorkbenchFlow.init({api,esc,notice,view,openLead:id=>{view('pipeline');loadLead(id).catch(e=>notice(e.message,true));}});
window.WorkbenchWorkspace.initialize();
window.WorkbenchSettings.init({api,esc,notice,refresh});
window.WorkbenchCampaigns.init({api,esc,stamp,notice,openDiscovery:()=>view('discovery'),openOperations:()=>view('operations'),openLead:id=>{view('pipeline');loadLead(id).catch(e=>notice(e.message,true));}});
const startUrl=new URL(location.href),startInPipeline=startUrl.hash!=='#campaigns'&&(startUrl.searchParams.has('prospect')||startUrl.searchParams.get('view')==='pipeline'||startUrl.hash==='#email-sequence');
if(startInPipeline){view('pipeline');refresh().then(()=>{if(!currentId){const requested=Number(startUrl.searchParams.get('prospect'));if(Number.isSafeInteger(requested)&&requested>0)return loadLead(requested);if(allLeads.length)return loadLead(allLeads[0].id);}}).catch(e=>notice(e.message,true));}
else{view('campaigns');refresh({reloadDetail:false,includeDiagnostics:false,includePipeline:false}).catch(e=>notice(e.message,true));}
setInterval(()=>{if(!document.hidden&&!$('#pipeline').hidden)refreshPipeline();},15000);
setInterval(()=>{if(!document.hidden&&!$('#campaigns').hidden)window.WorkbenchCampaigns.refresh();},30000);
