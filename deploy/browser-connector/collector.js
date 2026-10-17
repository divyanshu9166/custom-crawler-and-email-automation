(() => {
  if (globalThis.OutreachCollectorStop) globalThis.OutreachCollectorStop();
  let timer, stopped=false, previous='';
  const capture = async () => {
    if (stopped || document.visibilityState !== 'visible') return;
    const reference=globalThis.OutreachBusinessReader();
    if (!reference) return;
    const key=JSON.stringify([reference.source_url,reference.company,reference.website]);
    if (key===previous) return;
    const result=await chrome.runtime.sendMessage({type:'business-reference',reference});
    if (result?.saved) previous=key;
  };
  const observer=new MutationObserver(() => { clearTimeout(timer); timer=setTimeout(()=>capture().catch(()=>{}),800); });
  const listen=message => { if (message.type==='stop-collector') stop(); };
  const stop=() => { stopped=true; observer.disconnect(); clearTimeout(timer); document.removeEventListener('visibilitychange',capture); chrome.runtime.onMessage.removeListener(listen); };
  globalThis.OutreachCollectorStop=stop;
  chrome.runtime.onMessage.addListener(listen);
  observer.observe(document.body,{subtree:true,childList:true,characterData:true});
  document.addEventListener('visibilitychange',capture);
  capture().catch(()=>{});
})();
