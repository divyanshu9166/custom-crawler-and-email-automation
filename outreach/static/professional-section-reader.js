/* Only an explicitly requested person's visible Experience or Contact Info. */
({profile,section}) => {
  const u=new URL(location.href), expected=new URL(profile), suffix=section==='experience'?'/details/experience':'/overlay/contact-info';
  const visible=e=>!!e&&!e.closest('[hidden],[aria-hidden="true"]')&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden';
  if([...document.querySelectorAll('input[type="password"]')].some(visible)||/captcha|security check|sign in|authwall|just a moment/i.test(document.title)||/\/(login|authwall|checkpoint)(\/|$)/.test(u.pathname))return {state:'login_or_challenge'};
  if(!(u.hostname==='linkedin.com'||u.hostname.endsWith('.linkedin.com'))||u.pathname.replace(/\/$/,'')!==expected.pathname.replace(/\/$/,'')+suffix)return {state:'redirect_identity_mismatch'};
  let root;
  if(section==='contact_info'){
    root=[...document.querySelectorAll('dialog,[role="dialog"]')].filter(visible).find(d=>[...d.querySelectorAll('h1,h2,h3,[role="heading"]')].some(h=>visible(h)&&/^(?:contact info|contact information)$/i.test(h.innerText.trim())));
  }else if(section==='experience'){
    root=[...document.querySelectorAll('main section'),document.querySelector('main')].find(e=>visible(e)&&[...e.querySelectorAll('h1,h2,[role="heading"]')].some(h=>visible(h)&&/^experience$/i.test(h.innerText.trim())));
  }else return {state:'unsupported_section'};
  if(!root)return {state:'fields_not_ready'};
  const copy=root.cloneNode(true),original=[...root.querySelectorAll('*')],copies=[...copy.querySelectorAll('*')];
  original.forEach((e,i)=>{if(!visible(e)||e.matches('nav,aside,button,script,style,input')||e.closest('nav,aside,article')||(section==='experience'&&e.closest('dialog,[role="dialog"]')))copies[i]?.remove();});
  const text=copy.textContent.replace(/\s+/g,' ').trim().slice(0,6000),links=[],mailto=[];
  for(const a of root.querySelectorAll('a[href]'))if(visible(a)&&!a.closest('nav,aside,article'))try{
    if(a.href.startsWith('mailto:'))mailto.push(decodeURIComponent(a.href.slice(7).split('?')[0]));
    else {const v=new URL(a.href);if(['http:','https:'].includes(v.protocol)&&!v.username&&!v.password){v.search='';v.hash='';links.push(v.href);}}
  }catch{}
  return {state:'captured',text,links:[...new Set(links)].slice(0,40),mailto:[...new Set(mailto)].slice(0,20),source_url:u.origin+u.pathname,visibility:section==='contact_info'?'account_visible':'visible_profile'};
}
