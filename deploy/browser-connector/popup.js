const status=document.querySelector('#status');
const action=task=>async()=>{try{await task();}catch(e){status.textContent=e.message;}};
document.querySelector('#enable').onclick=action(async()=>{
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  const u=new URL(tab.url);
  if (u.protocol!=='https:' || !(u.hostname==='linkedin.com'||u.hostname.endsWith('.linkedin.com')||['x.com','www.x.com','twitter.com','www.twitter.com'].includes(u.hostname))) throw new Error('Open a LinkedIn company About page or public X business profile first.');
  if ((u.hostname==='linkedin.com'||u.hostname.endsWith('.linkedin.com')) ? !/^\/company\/[^/]+\/about\/?$/.test(u.pathname) : !/^\/[a-z0-9_]{1,15}\/?$/i.test(u.pathname)||['home','i','search','explore','messages','notifications','settings','compose','intent','login','tos','privacy'].includes(u.pathname.replaceAll('/','').toLowerCase())) throw new Error('This route is not a supported business page.');
  const {armed}=await chrome.storage.local.get('armed');
  if (armed && armed.tabId!==tab.id) await chrome.tabs.sendMessage(armed.tabId,{type:'stop-collector'}).catch(()=>{});
  await chrome.storage.local.set({armed:{tabId:tab.id,origin:u.origin}});
  await chrome.scripting.executeScript({target:{tabId:tab.id},files:['reader.js','collector.js']});
  status.textContent='Enabled for this tab. Missing/ambiguous business fields produce no capture.';
});
document.querySelector('#stop').onclick=action(async()=>{
  const {armed}=await chrome.storage.local.get('armed');
  await chrome.storage.local.remove('armed');
  if (armed) await chrome.tabs.sendMessage(armed.tabId,{type:'stop-collector'}).catch(()=>{});
  status.textContent='Collection stopped.';
});
document.querySelector('#export').onclick=action(async()=>{
  const {references=[]}=await chrome.storage.local.get('references');
  const blob=new Blob([JSON.stringify({format:'outreach-business-references-v1',references},null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob), a=document.createElement('a');a.href=url;a.download='outreach-business-references.json';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),10000);
  status.textContent=`Exported ${references.length} references. Import in Workbench → Find prospects.`;
});
chrome.storage.local.get('references').then(({references=[]})=>{status.textContent=`${references.length}/100 references stored locally.`;});
