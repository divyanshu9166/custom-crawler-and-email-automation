/* X public post search yields author hints, not confirmed business contacts. */
() => {
  const u=new URL(location.href),visible=e=>!!e&&!e.closest('nav,aside,dialog,[role="dialog"],[hidden],[aria-hidden="true"]')&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden';
  if([...document.querySelectorAll('input[type="password"]')].some(visible)||/captcha|security check|sign in|authwall|just a moment/i.test(document.title)||/\/i\/flow\/login/.test(u.pathname))return {state:'login_or_challenge',rows:[]};
  if(!['x.com','www.x.com'].includes(u.hostname)||u.pathname!=='/search'||u.searchParams.get('f')!=='live')return {state:'unsupported_route',rows:[]};
  const rows=[];
  for(const card of document.querySelectorAll('main article[data-testid="tweet"]')){
    if(!visible(card)||card.querySelector('[data-testid="socialContext"],[aria-label="Protected account"],[data-testid="icon-lock"]'))continue;
    const author=card.querySelector('[data-testid="User-Name"] a[href]'),body=card.querySelector('[data-testid="tweetText"]'),time=[...card.querySelectorAll('time[datetime]')].find(e=>!e.closest('[data-testid="quoteTweet"]')),permalink=time?.closest('a[href]');
    if(!visible(author)||!visible(body)||!visible(permalink)||author.closest('[data-testid="quoteTweet"]')||body.closest('[data-testid="quoteTweet"]'))continue;
    try{
      const a=new URL(author.href),post=new URL(permalink.href);
      if(a.protocol!=='https:'||post.protocol!=='https:'||a.username||a.password||a.port||post.username||post.password||post.port)continue;
      if(a.hostname!==u.hostname||post.hostname!==u.hostname||!/^\/[A-Za-z0-9_]{1,15}\/?$/.test(a.pathname)||!post.pathname.toLowerCase().startsWith(a.pathname.replace(/\/$/,'').toLowerCase()+'/status/'))continue;
      const copy=body.cloneNode(true),original=[...body.querySelectorAll('*')],copies=[...copy.querySelectorAll('*')];
      original.forEach((e,i)=>{if(!visible(e)||e.closest('[data-testid="quoteTweet"]'))copies[i]?.remove();});
      rows.push({url:a.origin+a.pathname.replace(/\/$/,''),title:author.innerText.trim().slice(0,150),snippet:copy.textContent.replace(/\s+/g,' ').trim().slice(0,1200),
        source_post_url:post.origin+post.pathname,indexed_signal_only:true,identity_verified:false});
    }catch{}
    if(rows.length>=100)break;
  }
  return {state:rows.length?'captured':'fields_not_ready',rows};
}
