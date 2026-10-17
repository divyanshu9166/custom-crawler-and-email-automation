/* Visible LinkedIn people cards. Search matches remain identity/buyer hints. */
() => {
  const u=new URL(location.href), visible=e=>!!e&&!e.closest('nav,aside,dialog,[role="dialog"],[hidden],[aria-hidden="true"]')&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden';
  if([...document.querySelectorAll('input[type="password"]')].some(visible)||/captcha|security check|sign in|authwall|just a moment/i.test(document.title)||/\/(login|checkpoint|authwall)(\/|$)/.test(u.pathname))return {state:'login_or_challenge',rows:[]};
  if(!(u.hostname==='linkedin.com'||u.hostname.endsWith('.linkedin.com'))||!/^\/search\/results\/people\/?$/.test(u.pathname))return {state:'unsupported_route',rows:[]};
  const clean=e=>{
    const copy=e.cloneNode(true), originals=[...e.querySelectorAll('*')], copies=[...copy.querySelectorAll('*')];
    originals.forEach((n,i)=>{if(!visible(n)||n.matches('button,script,style,input'))copies[i]?.remove();});
    return copy.textContent.replace(/\s+/g,' ').trim();
  };
  const root=document.querySelector('main .search-results-container,main [data-testid="search-results"],main [role="list"]');
  if(!visible(root))return {state:'fields_not_ready',rows:[]};
  const cards=[...root.querySelectorAll('.reusable-search__result-container,.entity-result,[data-testid="people-search-card"],[role="listitem"]')].filter(visible), rows=[], seen=new Set();
  for(const card of cards.slice(0,100)){
    for(const a of [...card.querySelectorAll('a[href]')].filter(visible)){
      try{
        const v=new URL(a.href), name=clean(a).replace(/\s*[•·]\s*(?:1st|2nd|3rd).*$/i,'').trim();
        if(v.protocol!=='https:'||v.username||v.password||v.port||!(v.hostname==='linkedin.com'||v.hostname.endsWith('.linkedin.com'))||!/^\/in\/[A-Za-z0-9_-]{2,100}\/?$/.test(v.pathname)||!name||/^(?:view|message|connect|follow)\b/i.test(name))continue;
        const url='https://www.linkedin.com'+v.pathname.replace(/\/$/,'');
        if(seen.has(url))continue;
        seen.add(url);rows.push({url,title:name.slice(0,150),snippet:clean(card).slice(0,1200),identity_verified:false,buyer_verified:false});break;
      }catch{}
    }
  }
  return {state:cards.length?'captured':'fields_not_ready',rows};
}
