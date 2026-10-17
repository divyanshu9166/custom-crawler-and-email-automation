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
  const companyVisible=e=>visible(e)&&!e.closest('nav,aside,article,[role="feed"],[role="listbox"]');
  let h=isX?(document.querySelector('main [data-testid="UserName"]')||document.querySelector('main h1')||[...document.querySelectorAll('h1')].find(e=>!e.closest('nav,aside')&&visible(e))):[...document.querySelectorAll('h1')].find(companyVisible);
  let name='',layout='',sections=[],anchors=[];
  if((host==='linkedin.com'||host.endsWith('.linkedin.com'))&&/^\/company\/[^/]+\/about\/?$/.test(u.pathname)){
    const fieldNames=new Set(['website','phone','email','industry','headquarters','company size','founded','specialties']);
    const current=Array.from(document.querySelectorAll('a[href]')).some(a=>visible(a)&&text(a).toLowerCase()==='about'&&new URL(a.href).pathname.replace(/\/$/,'')===u.pathname.replace(/\/$/,''));
    const dl=Array.from(document.querySelectorAll('dl')).find(e=>companyVisible(e)&&Array.from(e.querySelectorAll('dt')).some(d=>companyVisible(d)&&['website','industry'].includes(text(d).toLowerCase())));
    if(h&&text(h).length>=2&&current&&dl){
      name=text(h);layout='linkedin_definition_list';
      const overview=dl.previousElementSibling;
      if(overview?.tagName==='P'&&companyVisible(overview))sections.push(text(overview));
      for(const dt of dl.querySelectorAll('dt')){
        const dd=dt.nextElementSibling,label=text(dt).toLowerCase();
        if(companyVisible(dt)&&companyVisible(dd)&&dd.tagName==='DD'&&fieldNames.has(label)){
          sections.push(text(dt)+': '+text(dd));
          anchors.push(...Array.from(dd.querySelectorAll('a[href]')).filter(companyVisible));
        }
      }
    }else{
      // New rendered layout: company h2, Overview h2, then p/div field rows.
      // Scope ends at the next visible peer heading; never read posts or people.
      const main=document.querySelector('main');
      if(!main)return {state:'fields_not_ready',reason:'company_main_missing'};
      const headings=[...main.querySelectorAll('h1,h2,[role="heading"][aria-level="1"],[role="heading"][aria-level="2"]')].filter(companyVisible);
      const overviews=headings.filter(e=>text(e).toLowerCase()==='overview');
      if(overviews.length!==1)return {state:'fields_not_ready',reason:'company_overview_missing_or_ambiguous'};
      const overview=overviews[0],before=(a,b)=>!!(a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_FOLLOWING);
      const next=headings.find(e=>before(overview,e));
      const inOverview=e=>companyVisible(e)&&main.contains(e)&&before(overview,e)&&(!next||before(e,next));
      const companyHeadings=headings.filter(e=>before(e,overview)&&!['about','overview','locations'].includes(text(e).toLowerCase()));
      h=companyHeadings.at(-1);
      if(!h||text(h).length<2||text(h).length>200)return {state:'fields_not_ready',reason:'company_heading_missing'};
      name=text(h);
      const markerSelector='p,dt,h3,span,[role="term"]';
      const isMarker=e=>inOverview(e)&&!e.closest('a[href]')&&!e.querySelector('a[href]')&&fieldNames.has(text(e).toLowerCase());
      const markers=[...main.querySelectorAll(markerSelector)].filter(isMarker).filter(e=>![...e.querySelectorAll(markerSelector)].some(isMarker));
      const fields=new Map();
      for(const marker of markers){
        const label=text(marker).toLowerCase();
        let labelBox=marker,value=null,row=null;
        for(let depth=0;labelBox&&depth<4;depth++,labelBox=labelBox.parentElement){
          if(!inOverview(labelBox)||text(labelBox).toLowerCase()!==label)break;
          const candidate=labelBox.nextElementSibling,parent=labelBox.parentElement;
          if(!candidate||!inOverview(candidate)||!parent||parent.children.length>4)continue;
          if(candidate.querySelector('nav,aside,article,[role="feed"]')||candidate.matches('nav,aside,article,[role="feed"]')||[...candidate.querySelectorAll('h1,h2')].some(companyVisible))continue;
          if(parent.contains(overview)||(next&&parent.contains(next)))continue;
          if([candidate,...candidate.querySelectorAll(markerSelector)].some(e=>companyVisible(e)&&!e.closest('a[href]')&&!e.querySelector('a[href]')&&fieldNames.has(text(e).toLowerCase())))continue;
          const valueText=text(candidate);
          if(!valueText||valueText.length>2000)continue;
          value=candidate;row=parent;break;
        }
        if(!value)continue;
        if(fields.has(label)&&fields.get(label).value!==value)return {state:'fields_not_ready',reason:'ambiguous_company_field_rows'};
        fields.set(label,{marker,value,row});
      }
      if(fields.size<2||!['website','industry'].some(label=>fields.has(label)))return {state:'fields_not_ready',reason:'company_field_rows_missing'};
      const first=[...fields.values()][0].marker;
      const intro=[...main.querySelectorAll('p')].filter(e=>inOverview(e)&&before(e,first)&&!e.contains(first)&&text(e)&&![...e.querySelectorAll(markerSelector)].some(isMarker));
      sections.push(...intro.slice(0,2).map(text));
      for(const field of fields.values()){
        sections.push(text(field.marker)+': '+text(field.value));
        anchors.push(...[...field.value.querySelectorAll('a[href]'),...(field.value.matches('a[href]')?[field.value]:[])].filter(companyVisible));
      }
      layout='linkedin_overview_rows';
    }
  } else if(['x.com','www.x.com','twitter.com','www.twitter.com'].includes(host)&&/^\/[a-z0-9_]{1,15}\/?$/i.test(u.pathname)){
    if(!visible(h)||text(h).length<2)return {state:'fields_not_ready'};
    name=text(h);layout='x_profile_header';
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
  return {state:'captured',layout,url:u.origin+u.pathname.replace(/\/$/,''),title:name.slice(0,200),
    text:[name,...sections,emails.length?'Published mailto links: '+emails.join(', '):''].filter(Boolean).join('\n').slice(0,12000),
    links:[...new Set(links)].slice(0,30),mailto:emails.slice(0,30)};
}
