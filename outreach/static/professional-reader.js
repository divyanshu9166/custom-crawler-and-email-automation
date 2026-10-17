/* Visible LinkedIn top card/About/Experience; account chrome is excluded. */
options => {
  const includeExperience=options?.includeExperience!==false;
  const u=new URL(location.href),visible=e=>!!e&&!e.closest('nav,aside,article,[role="feed"],dialog,[role="dialog"],[aria-hidden="true"],[hidden]')&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';
  const text=e=>{
    if(!visible(e))return '';
    const clone=e.cloneNode(true),original=[...e.querySelectorAll('*')],copies=[...clone.querySelectorAll('*')];
    original.forEach((child,i)=>{if(!visible(child)||child.matches('button,script,style,input,nav,aside'))copies[i]?.remove();});
    return clone.textContent.replace(/\s+/g,' ').trim();
  };
  if([...document.querySelectorAll('input[type="password"]')].some(visible)||/captcha|security check|sign in|authwall|just a moment/i.test(document.title)||/\/(login|checkpoint|authwall|challenge)(\/|$)/i.test(u.pathname))return {state:'login_or_challenge'};
  if(!(u.hostname==='linkedin.com'||u.hostname.endsWith('.linkedin.com'))||!/^\/in\/[A-Za-z0-9_-]{2,100}\/?$/.test(u.pathname))return {state:'unsupported_route'};
  const h=[...document.querySelectorAll('main h1,main header h2,main [data-testid="profile-topcard"] h2')].find(e=>visible(e)&&!/^(about|experience|education|activity|suggested for you)$/i.test(text(e))),card=h?.closest('section,.top-card-layout,[data-testid="profile-topcard"]')||h?.closest('header');
  if(!visible(h)||!visible(card))return {state:'fields_not_ready'};
  const name=text(h),headline=card.querySelector('[data-testid="profile-headline"],.text-body-medium,.top-card-layout__headline');
  const pieces=[name,text(headline)],scopes=[card],sections={};
  for(const section of document.querySelectorAll('main section')){
    const heading=[...section.querySelectorAll('h2,[role="heading"]')].find(e=>visible(e)&&(includeExperience?['about','experience']:['about']).includes(text(e).toLowerCase()));
    if(!heading||section===card)continue;
    const key=text(heading).toLowerCase(),content=key==='about'?section.querySelector('[data-testid="profile-about"],.inline-show-more-text,.pv-shared-text-with-see-more')||section:section;
    if(visible(content)){const value=text(content).slice(0,6000);sections[key]={state:'captured',text:value,source_url:u.origin+u.pathname};pieces.push(value);scopes.push(content);}
  }
  const links=[],mailto=[];
  for(const scope of scopes)for(const a of scope.querySelectorAll('a[href]'))if(visible(a)){
    try{if(a.href.startsWith('mailto:'))mailto.push(decodeURIComponent(a.href.slice(7).split('?')[0]));
      else {const link=new URL(a.href);if(['https:','http:'].includes(link.protocol)&&!link.username&&!link.password){link.hash='';link.search='';links.push(link.href);}}}catch{}
  }
  if(!pieces.slice(1).some(Boolean))return {state:'fields_not_ready'};
  return {state:'captured',url:u.origin+u.pathname.replace(/\/$/,''),title:name.slice(0,150),headline:text(headline).slice(0,300),sections,
    text:[...pieces,mailto.length?'Published mailto links: '+mailto.join(', '):''].filter(Boolean).join('\n').slice(0,18000),
    links:[...new Set(links)].slice(0,30),mailto:mailto.slice(0,30)};
}
