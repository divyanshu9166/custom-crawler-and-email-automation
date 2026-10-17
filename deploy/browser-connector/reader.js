/* Scoped visible-business reader. This code performs no network requests. */
globalThis.OutreachBusinessReader = () => {
  const source = new URL(location.href);
  const host = source.hostname.toLowerCase();
  const visible = el => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
  const text = el => el?.textContent?.replace(/\s+/g, ' ').trim() || '';
  const website = value => {
    try {
      if (!/^https?:\/\//i.test(value)) {
        if (!/^(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:\/[^\s]*)?$/i.test(value)) return '';
        value = 'https://' + value;
      }
      const url = new URL(value);
      const d = url.hostname.toLowerCase();
      // Keep the URL credential guard explicit; this reads a property, not a stored secret.
      if (url.password) return '';
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.port ||
          !d.includes('.') || d.includes(':') || /^[\d.]+$/.test(d) || /\.(?:local|localhost|internal)$/.test(d) ||
          ['linkedin.com','x.com','twitter.com','t.co','google.com','facebook.com','instagram.com','youtube.com','bit.ly','linktr.ee']
            .some(p => d === p || d.endsWith('.'+p)) ||
          /\/(?:account|login|signin|checkout|cart)(?:\/|$)/i.test(url.pathname)) return '';
      url.search = ''; url.hash = '';
      return url.href;
    } catch { return ''; }
  };
  let name, links = [], labelOnly = false;
  if ((host === 'linkedin.com' || host.endsWith('.linkedin.com')) && /^\/company\/[^/]+\/about\/?$/.test(source.pathname)) {
    const heading = document.querySelector('h1');
    if (!visible(heading)) return null;
    name = text(heading);
    const currentAbout = Array.from(document.querySelectorAll('a[href]')).some(a => {
      try { return visible(a) && text(a).toLowerCase()==='about' && new URL(a.href).pathname.replace(/\/$/,'')===source.pathname.replace(/\/$/,''); } catch { return false; }
    });
    if (!currentAbout) return null; // SPA URL changed before the old header refreshed.
    // About definition lists only; navigation, employee cards and sidebars
    // cannot supply a website or company name.
    const fields = Array.from(document.querySelectorAll('dl dt')).filter(el => visible(el) && text(el).toLowerCase() === 'website');
    if (fields.length !== 1 || fields[0].nextElementSibling?.tagName !== 'DD') return null;
    links = Array.from(fields[0].nextElementSibling.querySelectorAll('a[href]')).filter(visible).map(a => website(a.href)).filter(Boolean);
  } else if (['x.com','www.x.com','twitter.com','www.twitter.com'].includes(host) && /^\/[a-z0-9_]{1,15}\/?$/i.test(source.pathname)) {
    const handle = source.pathname.replaceAll('/', '');
    if (['home','i','search','explore','messages','notifications','settings','compose','intent','login','tos','privacy'].includes(handle.toLowerCase())) return null;
    const heading = document.querySelector('h1');
    if (!visible(heading)) return null;
    name = text(heading);
    let scope = document.querySelector('[data-testid="UserProfileHeader_Items"]');
    if (!scope) {
      // Current public X layout: the Joined/About link and h1 share a small
      // header ancestor. Never expand into a post list or navigation shell.
      const about = Array.from(document.querySelectorAll('a[href]')).find(a => {
        try { const u=new URL(a.href); return visible(a) && ['x.com','twitter.com'].includes(u.hostname) && u.pathname.toLowerCase() === '/'+handle.toLowerCase()+'/about'; } catch { return false; }
      });
      let parent = about?.parentElement;
      for (let depth=0; parent && depth<5; depth++,parent=parent.parentElement) {
        if (parent.contains(heading) && !parent.querySelector('a[href*="/status/"]')) { scope=parent; break; }
      }
    }
    if (!scope || !visible(scope) || scope.querySelector('a[href*="/status/"]')) return null;
    for (const anchor of Array.from(scope.querySelectorAll('a[href]')).filter(visible)) {
      const direct = website(anchor.href);
      if (direct) links.push(direct);
      else {
        try {
          if (new URL(anchor.href).hostname === 't.co') {
            const candidate=website(text(anchor));
            if (candidate) { links.push(candidate); labelOnly=true; }
          }
        } catch { /* Opaque/invalid link stays unavailable. */ }
      }
    }
  } else return null;
  links = [...new Set(links)];
  if (!name || name.length<2 || name.length>200 || links.length!==1) return null;
  return {company:name,source_url:source.origin+source.pathname.replace(/\/$/,''),website:links[0],
    observed_at:Date.now()/1000,capture_method:'browser_connector_reference',
    observation:labelOnly?'The visible public profile website label supplies this website candidate; verify the current company page.':'The visible business About/profile website field links this website; verify company identity.'};
};
