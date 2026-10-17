/* Visible business DOM only. No hidden framework data, network responses or account navigation. */
() => {
  const u=new URL(location.href), host=u.hostname.toLowerCase();
  const visible=e=>!!e&&!e.closest('dialog,[role="dialog"],[aria-hidden="true"],[hidden]')&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';
  const text=e=>{
    if(!visible(e))return '';
    const clone=e.cloneNode(true),original=[...e.querySelectorAll('*')],copies=[...clone.querySelectorAll('*')];
    original.forEach((child,i)=>{if(!visible(child)||child.matches('button,script,style,input,nav,aside'))copies[i]?.remove();});
    return clone.textContent.replace(/\s+/g,' ').trim();
  };
  const passwords=Array.from(document.querySelectorAll('input[type="password"]')).some(visible);
  const title=document.title||'';
  if(passwords||/captcha|verify you are human|security check|sign in to linkedin|authwall|just a moment/i.test(title)||/\/(?:login|checkpoint|authwall|challenge|i\/flow\/login)(?:\/|$)/i.test(u.pathname))return {state:'login_or_challenge'};
  const isX=['x.com','www.x.com','twitter.com','www.twitter.com'].includes(host);
  const h=isX?(document.querySelector('main [data-testid="UserName"]')||document.querySelector('main h1')||[...document.querySelectorAll('h1')].find(e=>!e.closest('nav,aside')&&visible(e))):document.querySelector('h1');
  if(!visible(h)||text(h).length<2)return {state:'fields_not_ready'};
  let name=text(h);
  let sections=[],anchors=[];
  if((host==='linkedin.com'||host.endsWith('.linkedin.com'))&&/^\/company\/[^/]+\/about\/?$/.test(u.pathname)){
    const current=Array.from(document.querySelectorAll('a[href]')).some(a=>visible(a)&&text(a).toLowerCase()==='about'&&new URL(a.href).pathname.replace(/\/$/,'')===u.pathname.replace(/\/$/,''));
    if(!current)return {state:'fields_not_ready'};
    const dl=Array.from(document.querySelectorAll('dl')).find(e=>visible(e)&&Array.from(e.querySelectorAll('dt')).some(d=>text(d).toLowerCase()==='website'||text(d).toLowerCase()==='industry'));
    if(!dl)return {state:'fields_not_ready'};
    const overview=dl.previousElementSibling;
    if(overview?.tagName==='P'&&visible(overview))sections.push(text(overview));
    for(const dt of dl.querySelectorAll('dt')){
      const dd=dt.nextElementSibling,label=text(dt).toLowerCase();
      if(visible(dt)&&visible(dd)&&dd.tagName==='DD'&&['website','phone','email','industry','headquarters','company size','founded','specialties'].includes(label)){
        sections.push(text(dt)+': '+text(dd));
        anchors.push(...Array.from(dd.querySelectorAll('a[href]')).filter(visible));
      }
    }
  } else if(['x.com','www.x.com','twitter.com','www.twitter.com'].includes(host)&&/^\/[a-z0-9_]{1,15}\/?$/i.test(u.pathname)){
    const handle=u.pathname.replaceAll('/','').toLowerCase();
    if(['home','i','search','explore','messages','notifications','settings','compose','intent','login','tos','privacy'].includes(handle))return {state:'unsupported_route'};
    if(h.dataset.testid==='UserName'){
      const match=new RegExp('\\s*@'+handle+'\\b','i');
      if(!match.test(name))return {state:'profile_handle_mismatch'};
      name=name.split(match)[0].trim();
      if(name.length<2)return {state:'fields_not_ready'};
    }
    let scope=document.querySelector('[data-testid="UserProfileHeader_Items"]');
    const description=document.querySelector('[data-testid="UserDescription"]');
    if(visible(description))sections.push(text(description));
    if(!scope){
      const about=Array.from(document.querySelectorAll('a[href]')).find(a=>{try{return visible(a)&&new URL(a.href).pathname.toLowerCase()==='/'+handle+'/about';}catch{return false;}});
      let parent=about?.parentElement;
      for(let n=0;parent&&n<5;n++,parent=parent.parentElement)if(parent.contains(h)&&!parent.querySelector('a[href*="/status/"]')){scope=parent;break;}
    }
    if(!visible(scope)||scope.querySelector('a[href*="/status/"]'))return {state:'fields_not_ready'};
    sections.push(...Array.from(scope.querySelectorAll('p')).filter(visible).map(text));
    sections.push(...Array.from(scope.children).filter(e=>visible(e)&&e.classList.contains('whitespace-pre-wrap')).map(text));
    anchors=[...Array.from(scope.querySelectorAll('a[href]')),...(visible(description)?Array.from(description.querySelectorAll('a[href]')):[])].filter(visible);
  }else return {state:'unsupported_route'};
  const links=[],emails=[];
  for(const a of anchors){
    if(a.href.startsWith('mailto:')){try{emails.push(decodeURIComponent(a.href.slice(7).split('?')[0]));}catch{}continue;}
    let value=a.href;
    try{
      if(new URL(value).hostname==='t.co'&&/^(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:\/[^\s]*)?$/i.test(text(a)))value='https://'+text(a);
      const link=new URL(value);if(['http:','https:'].includes(link.protocol)&&!link.username&&!link.password){link.search='';link.hash='';links.push(link.href);}
    }catch{ /* Opaque links stay opaque and are filtered server-side. */ }
  }
  return {state:'captured',url:u.origin+u.pathname.replace(/\/$/,''),title:name.slice(0,200),
    text:[name,...sections,emails.length?'Published mailto links: '+emails.join(', '):''].filter(Boolean).join('\n').slice(0,12000),
    links:[...new Set(links)].slice(0,30),mailto:emails.slice(0,30)};
}
