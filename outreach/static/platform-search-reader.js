/* Read rendered search cards only; never account navigation or hidden responses. */
() => {
  const visible=e=>!!e&&!e.closest('dialog,[role="dialog"],[aria-hidden="true"],[hidden]')&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';
  const u=new URL(location.href),title=document.title||'';
  if(Array.from(document.querySelectorAll('input[type="password"]')).some(visible)||/captcha|verify you are human|security check|sign in|authwall|just a moment/i.test(title)||/\/(?:login|checkpoint|authwall|challenge|i\/flow\/login)(?:\/|$)/i.test(u.pathname))return {state:'login_or_challenge',rows:[]};
  let scopes=[];
  if((u.hostname==='linkedin.com'||u.hostname.endsWith('.linkedin.com'))&&u.pathname.replace(/\/$/,'')==='/search/results/companies'){
    const root=document.querySelector('main .search-results-container,main [data-testid="search-results"],main [role="list"]');
    if(visible(root))scopes=Array.from(root.querySelectorAll('.reusable-search__result-container,.entity-result,[data-testid="company-search-card"],[role="listitem"]')).filter(visible);
  }else if(['x.com','www.x.com','twitter.com','www.twitter.com'].includes(u.hostname)&&u.pathname==='/search'){
    scopes=Array.from(document.querySelectorAll('main [data-testid="UserCell"]')).filter(visible);
  }else return {state:'unsupported_route',rows:[]};
  if(!scopes.length)return {state:'fields_not_ready',rows:[]};
  const rows=[];
  const text=e=>{
    const copy=e.cloneNode(true),original=[...e.querySelectorAll('*')],clones=[...copy.querySelectorAll('*')];
    original.forEach((child,i)=>{if(!visible(child)||child.matches('button,script,style,input,nav,aside'))clones[i]?.remove();});
    return copy.textContent.replace(/\s+/g,' ').trim();
  };
  for(const scope of scopes.slice(0,200))for(const a of scope.querySelectorAll('a[href]'))if(visible(a)){
    const label=a.textContent.replace(/\s+/g,' ').trim();
    if(label)rows.push({url:a.href,title:label.slice(0,200),snippet:text(scope).slice(0,1200)});
  }
  return {state:'captured',rows};
}
