/* Public LinkedIn top card/About only; no contact overlay, connections or timeline. */
() => {
  const u=new URL(location.href),visible=e=>!!e&&!e.closest('dialog,[role="dialog"],[aria-hidden="true"],[hidden]')&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';
  const text=e=>{
    if(!visible(e))return '';
    const clone=e.cloneNode(true),original=[...e.querySelectorAll('*')],copies=[...clone.querySelectorAll('*')];
    original.forEach((child,i)=>{if(!visible(child)||child.matches('button,script,style,input,nav,aside'))copies[i]?.remove();});
    return clone.textContent.replace(/\s+/g,' ').trim();
  };
  if([...document.querySelectorAll('input[type="password"]')].some(visible)||/captcha|security check|sign in|authwall|just a moment/i.test(document.title)||/\/(login|checkpoint|authwall|challenge)(\/|$)/i.test(u.pathname))return {state:'login_or_challenge'};
  if(!(u.hostname==='linkedin.com'||u.hostname.endsWith('.linkedin.com'))||!/^\/in\/[A-Za-z0-9_-]{2,100}\/?$/.test(u.pathname))return {state:'unsupported_route'};
  const h=document.querySelector('main h1'),card=h?.closest('section,.top-card-layout');
  if(!visible(h)||!visible(card))return {state:'fields_not_ready'};
  const name=text(h),headline=card.querySelector('[data-testid="profile-headline"],.text-body-medium,.top-card-layout__headline');
  const pieces=[name,text(headline)],scopes=[card];
  for(const section of document.querySelectorAll('main section')){
    const heading=[...section.querySelectorAll('h2')].find(e=>visible(e)&&text(e).toLowerCase()==='about');
    if(!heading)continue;
    const content=section.querySelector('[data-testid="profile-about"],.inline-show-more-text,.pv-shared-text-with-see-more');
    if(visible(content)){pieces.push(text(content));scopes.push(content);}
  }
  const links=[],mailto=[];
  for(const scope of scopes)for(const a of scope.querySelectorAll('a[href]'))if(visible(a)){
    try{if(a.href.startsWith('mailto:'))mailto.push(decodeURIComponent(a.href.slice(7).split('?')[0]));
      else {const link=new URL(a.href);if(['https:','http:'].includes(link.protocol)&&!link.username&&!link.password){link.hash='';link.search='';links.push(link.href);}}}catch{}
  }
  if(!pieces.slice(1).some(Boolean))return {state:'fields_not_ready'};
  return {state:'captured',url:u.origin+u.pathname.replace(/\/$/,''),title:name.slice(0,150),headline:text(headline).slice(0,300),
    text:[...pieces,mailto.length?'Published mailto links: '+mailto.join(', '):''].filter(Boolean).join('\n').slice(0,12000),
    links:[...new Set(links)].slice(0,30),mailto:mailto.slice(0,30)};
}
