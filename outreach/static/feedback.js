/* Shared action feedback. Queue acceptance is separate from actual job execution. */
window.WorkbenchFeedback = (() => {
  const key = 'workbench-activity-v1', jobs = new Map(), busy = new WeakMap(), toasts = new Map();
  let cfg, origin, originAt = 0, polling = false, timer, latestJob, returnFocus, lastRender = '';
  const el = (tag, text, cls) => {const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  const names = {discover:'Prospect search',research:'Business research',prepare:'Email preparation',verify:'Mailbox verification',
    screenshot:'Desktop & mobile audit',performance:'PageSpeed audit',contact_research:'Public contact research',
    professional_research:'Professional profile research',social_research:'Public post research'};
  const active = j => ['pending','running'].includes(j.state);
  let stack, panel, list, toggle, count, connection;

  function message(text, tone='success', title, action) {
    if(!stack)return;
    const id=action?.jobId?'job-'+action.jobId:'notice';
    const old=toasts.get(id);if(old&&old.text===text&&old.tone===tone&&old.title===title)return;
    if(old){clearTimeout(old.timer);old.node.remove();}
    const card=el('section',null,'feedback-toast '+tone);card.dataset.tone=tone;
    card.setAttribute('role',tone==='error'?'alert':'status');
    const icon=el('span',tone==='error'?'!':tone==='success'?'✓':tone==='loading'?'':'i','feedback-icon');
    icon.setAttribute('aria-hidden','true');
    const content=el('div',null,'feedback-content');
    content.append(el('strong',title||({error:'Action needs attention',warning:'Check this result',loading:'Working on your request',info:'Update',success:'Done'}[tone])),el('p',text));
    if(action){const b=el('button','View progress','feedback-link');b.type='button';b.onclick=open;content.append(b);}
    const close=el('button','×','feedback-dismiss');close.type='button';close.setAttribute('aria-label','Dismiss notification');
    close.onclick=()=>{clearTimeout(toasts.get(id)?.timer);card.remove();toasts.delete(id);};
    card.append(icon,content,close);stack.append(card);
    const entry={node:card,text,tone,title};toasts.set(id,entry);
    if(!['error','loading'].includes(tone))entry.timer=setTimeout(()=>{card.remove();toasts.delete(id);},9000);
    while(toasts.size>3){const first=toasts.keys().next().value;const v=toasts.get(first);clearTimeout(v.timer);v.node.remove();toasts.delete(first);}
  }

  function description(j) {
    if(j.unavailable)return 'Status unavailable. The job may still be running; no request has been repeated.';
    if(j.state==='pending')return !j.worker_enabled?'Research automation is OFF. Enable it in Settings to process queued jobs.':
      j.due_at*1000>Date.now()+2000?'Waiting for its next attempt at '+new Date(j.due_at*1000).toLocaleTimeString()+'.':'Waiting for an available worker. You can continue using the dashboard.';
    if(j.state==='running'){
      const stages={google_maps_search:'Searching public Google listings',google_business_check:'Checking a Google business listing',
        search:'Searching business sources',resolve:'Checking business identity and website matches',query_started:'Searching a business source',
        query_finished:'Search source checked',query_failed:'A search source returned an error'};
      return (stages[j.progress?.stage]||'Processing the saved job')+(j.progress?.company?' · '+j.progress.company:'')+
        (Number.isInteger(j.progress?.retained)?' · '+j.progress.retained+' candidates retained in this pass':'')+
        (Number.isInteger(j.progress?.candidate_domains)?' · '+j.progress.candidate_domains+' website candidates':'')+'.';
    }
    if(j.state==='done')return j.kind==='discover'?
      (Number.isInteger(j.saved_prospects)?j.saved_prospects+' prospects saved. ':'')+'Search finished; detailed research or audits may still be queued. Open Pipeline to review results.':
      j.error||'This job finished. Review its saved result; completion does not imply qualification or sending approval.';
    return j.error||(j.state==='cancelled'?'This job was cancelled.':'Open Operations for the recorded failure and retry controls.');
  }
  function stateLabel(j){return j.unavailable?'Status unavailable':j.state==='pending'?(j.worker_enabled?'Queued':'Queued · research OFF'):
    j.state==='running'?'Running':j.state==='done'?'Completed':j.state==='missing'?'Not found':j.state==='cancelled'?'Cancelled':'Failed';}
  function showJob(j){if(!panel.hidden)return;message(description(j),j.unavailable?'warning':j.state==='failed'?'error':j.state==='cancelled'?'warning':
    j.state==='done'?'success':'info',(names[j.kind]||j.title||'Background task')+' · '+stateLabel(j),{jobId:j.id});}
  function save(){try{sessionStorage.setItem(key,JSON.stringify([...jobs.values()].slice(-20).map(j=>({id:j.id,title:j.title,kind:j.kind,state:j.state,worker_enabled:j.worker_enabled}))));}catch{/* Tracking still works without browser storage. */}}
  function render(){
    const rows=[...jobs.values()].reverse(),pending=rows.filter(active).length;
    const unavailable=rows.some(j=>j.unavailable);
    count.textContent=unavailable?'!':pending?String(pending):'';count.hidden=!pending&&!unavailable;
    toggle.setAttribute('aria-label',unavailable?'Activity, status updates unavailable':pending?'Activity, '+pending+' active jobs':'Activity');
    const signature=JSON.stringify(rows);if(signature===lastRender)return;lastRender=signature;
    list.replaceChildren();
    if(!rows.length){list.append(el('p','Jobs started from this tab appear here. You can also view all research jobs in Operations.','feedback-empty'));return;}
    for(const j of rows){
      const card=el('article',null,'activity-job');card.dataset.jobId=j.id;
      const head=el('div',null,'activity-job-heading');head.append(el('strong',names[j.kind]||j.title||'Background task'),el('span',stateLabel(j),'activity-state '+j.state));
      card.append(head,el('small','Job #'+j.id+(j.query?' · '+j.query:'')),el('p',description(j)));
      if(j.kind==='discover'&&j.state==='done'||j.lead_id){const b=el('button',j.lead_id?'Open prospect':'Open Pipeline','feedback-link');b.type='button';b.onclick=()=>{close();if(j.lead_id)cfg.openLead(j.lead_id);else cfg.view('pipeline');};card.append(b);}
      list.append(card);
    }
  }
  function open(){returnFocus=document.activeElement;panel.hidden=false;toggle.setAttribute('aria-expanded','true');
    for(const [id,v] of toasts)if(id.startsWith('job-')){clearTimeout(v.timer);v.node.remove();toasts.delete(id);}
    render();panel.querySelector('[data-close-activity]').focus();poll();}
  function close(){panel.hidden=true;toggle.setAttribute('aria-expanded','false');if(returnFocus?.isConnected)returnFocus.focus();else toggle.focus();}
  function originButton(){return origin?.isConnected&&Date.now()-originAt<1500?origin:null;}
  function action(){
    const button=originButton();if(!button)return ()=>{};
    const aria=button.getAttribute('aria-busy'),disabled=button.getAttribute('aria-disabled');
    button.dataset.actionPending='true';button.setAttribute('aria-busy','true');button.setAttribute('aria-disabled','true');
    return ()=>{delete button.dataset.actionPending;
      if(aria===null)button.removeAttribute('aria-busy');else button.setAttribute('aria-busy',aria);
      if(disabled===null)button.removeAttribute('aria-disabled');else button.setAttribute('aria-disabled',disabled);
    };
  }
  function lock(button){
    if(!button)return ()=>{};
    const current=busy.get(button);
    if(current){current.count++;return ()=>unlock(button);}
    busy.set(button,{count:1,disabled:button.disabled,aria:button.getAttribute('aria-busy')});
    button.dataset.busy='true';button.setAttribute('aria-busy','true');button.disabled=true;
    return ()=>unlock(button);
  }
  function unlock(button){const v=busy.get(button);if(!v||--v.count)return;
    delete button.dataset.busy;if(v.aria===null)button.removeAttribute('aria-busy');else button.setAttribute('aria-busy',v.aria);
    if(!v.disabled)button.disabled=false;busy.delete(button);
  }
  function begin(path,method){
    const button=originButton();origin=null;
    return {path:path.split('?')[0],method,button,release:lock(button)};
  }
  function track(id,title,kind,announce=true){
    if(!Number.isSafeInteger(id)||id<1)return;
    if(!jobs.has(id))jobs.set(id,{id,title,kind,state:'pending',worker_enabled:!!cfg.workerEnabled()});
    latestJob={id,at:Date.now()};
    while(jobs.size>20){const finished=[...jobs.values()].find(j=>!active(j));jobs.delete(finished?.id||jobs.keys().next().value);}
    save();render();if(announce)showJob(jobs.get(id));poll();
  }
  function finish(request,result){
    request.release();
    if(Number.isSafeInteger(result?.job_id)){
      const kind=request.path==='/api/discover'?'discover':/\/(?:prepare|preparation)$/.test(request.path)?'prepare':
        /\/performance$/.test(request.path)?'performance':/\/screenshot$/.test(request.path)?'screenshot':
        /\/verify$/.test(request.path)?'verify':/\/research(?:-more)?$/.test(request.path)||request.path==='/api/leads'||request.path==='/api/profile-leads'?'research':undefined;
      track(result.job_id,request.button?.textContent?.trim()||'Background task',kind);return;
    }
    if(Array.isArray(result?.queued)){
      for(const row of result.queued.slice(0,20))if(row.job_id)track(row.job_id,'Email preparation','prepare',false);
      latestJob=null;
      message(result.queued.length+' jobs queued; '+(result.skipped?.length||0)+' prospects need attention.'+(result.queued.length>20?' Latest 20 jobs are shown in Activity.':''),result.skipped?.length?'warning':'success','Batch preparation accepted');return;
    }
    if(request.method!=='GET')latestJob=null;
    if(typeof result?.ready==='boolean'){message(result.note||result.reason||'Review the provider result.',result.ready?'success':'warning',result.ready?'Connection check passed':'Connection could not be verified');return;}
    if(request.method==='GET')return;
    if(request.path==='/api/logout'||request.path==='/api/settings/credentials'){jobs.clear();try{sessionStorage.removeItem(key);}catch{}return;}
    const labels={'/api/settings/writer':'AI writer settings saved','/api/settings/mail':'Mailbox settings saved','/api/settings/research':'Research preferences saved',
      '/api/settings/runtime':'Automation controls saved','/api/schedules':'Recurring search saved','/api/campaigns':'Campaign created',
      '/api/pause':'Sending paused','/api/resume':'Sending resumed'};
    const partial=result?.errors?.length||result?.results?.some(r=>r.ok===false);
    message(partial?'Some records need attention. Review the results beside this action.':'Your request was accepted. Review any details shown beside this action.',partial?'warning':'success',labels[request.path]||'Request accepted');
  }
  function fail(request,error){request.release();message(error.message||'The request could not be completed.','error');}
  function notice(text,bad){
    if(!text)return;
    if(!bad&&latestJob&&Date.now()-latestJob.at<12000&&/queued|search scheduled/i.test(text)&&jobs.has(latestJob.id)){
      const n=toasts.get('notice');if(n){clearTimeout(n.timer);n.node.remove();toasts.delete('notice');}showJob(jobs.get(latestJob.id));return;
    }
    const loading=/^(?:Working|Checking verifier|Queuing preparation)\u2026/.test(text);
    const warning=/\bneeds attention\b|\b[1-9]\d* (?:prospects|rows|records) need attention\b|refresh failed|could not|unavailable/i.test(text);
    message(text,bad&&/refresh failed/i.test(text)?'warning':bad?'error':loading?'loading':warning?'warning':'success');
  }
  async function poll(){
    clearTimeout(timer);if(polling||document.hidden)return;
    const targets=[...jobs.values()].filter(j=>active(j)||j.unavailable);
    if(!targets.length)return;
    polling=true;let unavailable=false;
    try{
      // Bound concurrent reads; never repeat a mutation on a connection failure.
      for(let i=0;i<targets.length;i+=4)await Promise.all(targets.slice(i,i+4).map(async old=>{
        try{
          const result=await cfg.api('/api/jobs/'+old.id,'GET',undefined,{feedback:false});
          const updated={...result,title:old.title};jobs.set(old.id,updated);
          if(old.state!==result.state||old.unavailable)showJob(updated);
          if(old.state!=='done'&&result.state==='done')Promise.resolve(cfg.completed?.()).catch(()=>message('The job finished, but the dashboard could not refresh. Your saved result is preserved.','warning','Refresh needed'));
        }catch(e){
          if(e.status===404){const missing={...old,state:'missing',unavailable:false,error:'This job is no longer available. No work has been repeated.'};jobs.set(old.id,missing);showJob(missing);}
          else{unavailable=true;jobs.set(old.id,{...old,unavailable:true});}
        }
      }));
      connection.textContent=unavailable?'Activity updates are unavailable. Existing jobs may still be running. Check your connection; no work was resubmitted.':'';
      render();save();
    }finally{polling=false;if([...jobs.values()].some(j=>active(j)||j.unavailable))timer=setTimeout(poll,unavailable?15000:5000);}
  }
  function init(options){
    cfg=options;
    stack=el('div',null,'feedback-stack');stack.id='feedback-notifications';stack.setAttribute('aria-label','Notifications');
    panel=el('aside',null,'activity-panel');panel.id='activity-panel';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-labelledby','activity-heading');
    const head=el('div',null,'activity-panel-heading'),title=el('div');title.append(el('span','WORKSPACE ACTIVITY','eyebrow'));
    const heading=el('h2','Your background jobs');heading.id='activity-heading';title.append(heading);
    const closeButton=el('button','×','feedback-dismiss');closeButton.type='button';closeButton.dataset.closeActivity='';closeButton.setAttribute('aria-label','Close activity');closeButton.onclick=close;head.append(title,closeButton);
    connection=el('p',null,'activity-connection');connection.setAttribute('role','status');list=el('div',null,'activity-jobs');
    const note=el('p','Latest 20 jobs started from this tab. Search completion is separate from research, qualification and email approval.','small');
    const operations=el('button','Open Operations','feedback-link');operations.type='button';operations.onclick=()=>{close();cfg.view('operations');};
    const check=el('button','Check status','feedback-link');check.type='button';check.onclick=poll;
    panel.append(head,note,connection,check,list,operations);document.body.append(stack,panel);
    toggle=el('button',null,'activity-toggle');toggle.id='activity-toggle';toggle.type='button';toggle.append(el('span','Activity'));count=el('span',null,'activity-count');toggle.append(count);
    toggle.setAttribute('aria-controls','activity-panel');toggle.setAttribute('aria-expanded','false');toggle.onclick=()=>panel.hidden?open():close();document.querySelector('#logout').before(toggle);
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden)close();});
    document.addEventListener('click',event=>{
      const target=event.target.closest('button');
      if(target?.dataset.actionPending){event.preventDefault();event.stopImmediatePropagation();return;}
      if(target&&!target.closest('.feedback-stack,.activity-panel')&&target!==toggle){origin=target;originAt=Date.now();}
      const link=event.target.closest('a[href]');if(link&&/^\/api\/.*export/.test(link.getAttribute('href')))message('Export requested. Your browser will handle the file or preview.','info','Opening export');
    },true);
    document.addEventListener('submit',event=>{
      const button=event.submitter||event.target.querySelector('button[type=submit],button:not([type])');
      if(button?.dataset.actionPending){event.preventDefault();event.stopImmediatePropagation();return;}
      origin=button;originAt=Date.now();
    },true);
    document.addEventListener('invalid',event=>{const form=event.target.form;if(form)message(event.target.validationMessage||'Complete the required fields.','warning','Check this form');},true);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
    try{const stored=JSON.parse(sessionStorage.getItem(key)||'[]');if(Array.isArray(stored))for(const j of stored.slice(-20))if(Number.isSafeInteger(j.id)&&j.id>0)jobs.set(j.id,{id:j.id,title:String(j.title||'Background task').slice(0,80),kind:j.kind,state:j.state,worker_enabled:j.worker_enabled});}catch{}
    render();poll();
  }
  return {init,begin,finish,fail,notice,message,open,poll,action};
})();
