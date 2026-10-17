/* Bounded normal search UI interaction; no API calls or access-control recovery. */
({allowNext}) => {
  const u=new URL(location.href),visible=e=>!!e&&!e.closest('dialog,[role="dialog"],[hidden],[aria-hidden="true"]')&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';
  const linkedin=(u.hostname==='linkedin.com'||u.hostname.endsWith('.linkedin.com'))&&/^\/search\/results\/(companies|people)$/.test(u.pathname.replace(/\/$/,''));
  const x=['x.com','www.x.com','twitter.com','www.twitter.com'].includes(u.hostname)&&u.pathname==='/search';
  if(!linkedin&&!x)return {action:'unsupported_route'};
  if([...document.querySelectorAll('input[type="password"]')].some(visible)||/captcha|security check|sign in|authwall|just a moment/i.test(document.title))return {action:'login_or_challenge'};
  const scroll=()=>{
    const r=document.querySelector('main')?.getBoundingClientRect();
    const top=Math.max(0,r?.top||0),bottom=Math.min(innerHeight,r?.bottom||innerHeight);
    return {action:'scroll',deltaY:Math.max(400,innerHeight*.8),
      x:Math.max(1,Math.min(innerWidth-1,r?(r.left+r.right)/2:innerWidth/2)),
      y:bottom>top?(top+bottom)/2:innerHeight*.6};
  };
  if(document.documentElement.scrollHeight>scrollY+innerHeight+5){
    return scroll();
  }
  if(linkedin){
    const buttons=[...document.querySelectorAll('main .artdeco-pagination button,main [aria-label="Pagination"] button,main [aria-label="pagination"] button')];
    const next=buttons.find(e=>visible(e)&&!e.disabled&&e.getAttribute('aria-disabled')!=='true'&&
      (e.matches('.artdeco-pagination__button--next')||/^next(?: page)?$/i.test(e.getAttribute('aria-label')||e.textContent.trim())));
    if(next){if(!allowNext)return {action:'page_budget'};next.click();return {action:'next_page'};}
    return {action:'no_more_results'};
  }
  // At the bottom an X search may append another public UserCell batch.
  return scroll();
}
