/* Author-scoped visible public post cards; quoted posts/reposts are excluded. */
({profile,limit}) => {
  const u=new URL(location.href),target=new URL(profile),visible=e=>!!e&&!e.closest('nav,aside,dialog,[role="dialog"],[hidden],[aria-hidden="true"]')&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden';
  if([...document.querySelectorAll('input[type="password"]')].some(visible)||/captcha|security check|sign in|authwall|just a moment/i.test(document.title)||/\/(login|checkpoint|authwall|i\/flow\/login)(\/|$)/.test(u.pathname))return {state:'login_or_challenge',posts:[]};
  const linkedin=target.hostname==='linkedin.com'||target.hostname.endsWith('.linkedin.com'),same=(u.hostname===target.hostname||(linkedin&&(u.hostname==='linkedin.com'||u.hostname.endsWith('.linkedin.com'))));
  if(!same||u.pathname.replace(/\/$/,'')!==target.pathname.replace(/\/$/,'')+(linkedin?'/posts':''))return {state:'redirect_identity_mismatch',posts:[]};
  if(!linkedin&&[...document.querySelectorAll('main [data-testid="UserName"] [aria-label="Protected account"],main [data-testid="UserName"] [data-testid="icon-lock"],main [data-testid="User-Name"] [aria-label="Protected account"]')].some(visible))return {state:'protected_profile',posts:[]};
  const clean=e=>{
    if(!visible(e)||e.closest('[data-testid="quoteTweet"],.feed-shared-mini-update-v2'))return '';
    const c=e.cloneNode(true),original=[...e.querySelectorAll('*')],copies=[...c.querySelectorAll('*')];
    original.forEach((n,i)=>{if(!visible(n)||n.matches('button,script,style,input')||n.closest('[data-testid="quoteTweet"],.feed-shared-mini-update-v2'))copies[i]?.remove();});
    return c.textContent.replace(/\s+/g,' ').trim();
  };
  const cards=[...document.querySelectorAll(linkedin?'main [data-urn^="urn:li:activity:"],main [data-testid="feed-update"],main article':'main article[data-testid="tweet"]')].filter(visible),posts=[],seen=new Set();
  for(const card of cards.slice(0,60)){
    if(card.querySelector('[data-testid="socialContext"],.update-components-header'))continue;
    if(card.querySelector('[aria-label="Protected account"],[data-testid="icon-lock"]'))continue;
    const actor=card.querySelector(linkedin?'.update-components-actor a[href*="/company/"],[data-testid="actor-name"][href]':'[data-testid="User-Name"] a[href]');
    if(!visible(actor)||actor.closest('[data-testid="quoteTweet"],.feed-shared-mini-update-v2'))continue;
    try{
      const owner=new URL(actor.href);
      if(owner.protocol!=='https:'||owner.username||owner.password||owner.port)continue;
      if(owner.hostname!==target.hostname&&!(linkedin&&(owner.hostname==='linkedin.com'||owner.hostname.endsWith('.linkedin.com'))))continue;
      if(owner.pathname.replace(/\/$/,'').toLowerCase()!==target.pathname.replace(/\/$/,'').toLowerCase())continue;
    }catch{continue;}
    const text=clean(card.querySelector(linkedin?'.update-components-text,.feed-shared-update-v2__description,[data-testid="post-text"]':'[data-testid="tweetText"]'));if(!text)continue;
    const time=[...card.querySelectorAll('time[datetime]')].find(e=>!e.closest('[data-testid="quoteTweet"],.feed-shared-mini-update-v2')),anchor=linkedin?[...card.querySelectorAll('a[href]')].find(a=>!a.closest('.feed-shared-mini-update-v2')&&/\/feed\/update\/urn:li:activity:\d+|\/posts\/[^/]+-activity-\d+/.test(a.href)):time?.closest('a[href]');
    let url;
    try{
      if(anchor){const v=new URL(anchor.href);v.search='';v.hash='';url=v.href;}
      else if(linkedin&&/^urn:li:activity:\d+$/.test(card.getAttribute('data-urn')||''))url='https://www.linkedin.com/feed/update/'+card.getAttribute('data-urn')+'/';
      else continue;
      const v=new URL(url);
      if(v.protocol!=='https:'||v.username||v.password||v.port)continue;
      if(linkedin){if(!(v.hostname==='linkedin.com'||v.hostname.endsWith('.linkedin.com'))||!/^\/(?:feed\/update\/urn:li:activity:\d+\/?|posts\/[^/]+-activity-\d+[^/]*)$/.test(v.pathname))continue;}
      else if(v.hostname!==target.hostname||!new RegExp('^/'+target.pathname.split('/')[1]+'/status/[0-9]+/?$','i').test(v.pathname))continue;
    }catch{continue;}
    if(seen.has(url))continue;seen.add(url);
    const date=time?.getAttribute('datetime'),published=date&&!Number.isNaN(Date.parse(date))?date:null;
    posts.push({url,author_url:profile,text:text.slice(0,6000),published_at:published,publication_date_verified:!!published,identity_verified:false,review_required:true});
    if(posts.length>=Math.max(1,Math.min(10,limit)))break;
  }
  return {state:posts.length?'captured':cards.length?'no_author_matched_posts':'fields_not_ready',posts};
}
