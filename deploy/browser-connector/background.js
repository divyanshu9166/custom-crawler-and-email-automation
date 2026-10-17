const serial = task => { const result=serial.pending.then(task,task); serial.pending=result.catch(()=>{}); return result; };
serial.pending=Promise.resolve();
chrome.runtime.onMessage.addListener((message,sender,respond) => {
  if (message.type!=='business-reference') return;
  serial(async()=>{
    const state=await chrome.storage.local.get(['armed','references']);
    const ref=message.reference;
    if (!sender.tab || state.armed?.tabId!==sender.tab.id || new URL(sender.url).origin!==state.armed.origin ||
        !ref || ref.capture_method!=='browser_connector_reference' || typeof ref.company!=='string' || ref.company.length>200 ||
        typeof ref.observation!=='string' || ref.observation.length>300 || !Number.isFinite(ref.observed_at) ||
        !['source_url','website'].every(k=>typeof ref[k]==='string' && ref[k].length<=2000)) return {saved:false};
    const page=new URL(sender.url), source=new URL(ref.source_url);
    if (source.origin!==page.origin || source.pathname.replace(/\/$/,'')!==page.pathname.replace(/\/$/,'')) return {saved:false};
    const clean=Object.fromEntries(['company','source_url','website','observed_at','observation','capture_method'].map(k=>[k,ref[k]]));
    const references=state.references || [];
    const key=r=>JSON.stringify([r.source_url,r.company,r.website]);
    if (references.some(r=>key(r)===key(clean))) return {saved:true};
    if (references.length>=100) return {saved:false,error:'Buffer full. Export the references.'};
    await chrome.storage.local.set({references:[...references,clean]});
    return {saved:true};
  }).then(respond,()=>respond({saved:false}));
  return true;
});
chrome.tabs.onUpdated.addListener((tabId,change,tab)=>{
  if (change.status!=='complete') return;
  serial(async()=>{
    const {armed}=await chrome.storage.local.get('armed');
    if (armed?.tabId!==tabId) return;
    if (!tab.url || new URL(tab.url).origin!==armed.origin) { await chrome.storage.local.remove('armed'); return; }
    try { await chrome.scripting.executeScript({target:{tabId},files:['reader.js','collector.js']}); }
    catch { await chrome.storage.local.remove('armed'); }
  });
});
chrome.tabs.onRemoved.addListener(tabId=>serial(async()=>{
  const {armed}=await chrome.storage.local.get('armed');
  if (armed?.tabId===tabId) await chrome.storage.local.remove('armed');
}));
