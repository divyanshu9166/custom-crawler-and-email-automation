() => {
  const visible = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility === 'visible' &&
      (!el.checkVisibility || el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})) &&
      Number(s.opacity) !== 0 && !el.closest('[hidden],[aria-hidden="true"]');
  };
  const selector = el => {
    if (el.id) return '#'+CSS.escape(el.id);
    const parts = [];
    let node=el;
    for (; node && node!==document.body && parts.length<20; node=node.parentElement) {
      parts.unshift(node.tagName.toLowerCase()+':nth-of-type('+([...node.parentElement.children]
        .filter(n=>n.tagName===node.tagName).indexOf(node)+1)+')');
    }
    return (node===document.body ? 'body > ' : 'body ')+parts.join(' > ');
  };
  const text = el => (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\s+/g,' ').slice(0,100);
  const ctas = [...document.querySelectorAll('a[href]')].filter(el => visible(el) &&
    /quote|contact|enquir|inquir|book|appointment|checkout|shop|product/i.test(text(el)))
    .slice(0,30).map(el=>({selector:selector(el),label:text(el),url:el.href}));
  const controls = [];
  for (const form of [...document.forms].filter(visible)) {
    const fields = [...form.querySelectorAll('input,select,textarea')].filter(el =>
      visible(el) && !el.disabled && !el.readOnly && !['hidden','submit','button','reset','checkbox','radio','search'].includes(el.type));
    const actions = [...form.querySelectorAll('button,input[type=submit]')].map(el=>text(el)||el.value).join(' ');
    const relevant = /quote|enquir|inquir|book|appointment|contact|checkout/i.test(actions) ||
      (fields.some(el=>el.tagName==='TEXTAREA') && fields.some(el=>el.type==='email'));
    if (!relevant) continue;
    for (const field of fields) {
      const named = [...(field.labels || [])].some(el=>el.textContent.trim()) ||
        (field.getAttribute('aria-label') || '').trim() || (field.title || '').trim() ||
        (field.getAttribute('aria-labelledby') || '').split(/\s+/).some(id=>document.getElementById(id)?.textContent.trim());
      if (!named) controls.push({selector:selector(field),type:field.type || field.tagName.toLowerCase(),
        hint:(field.getAttribute('placeholder') || field.name || field.type || 'field').slice(0,60)});
    }
  }
  const stylesReady = [...document.querySelectorAll('link[rel~=stylesheet]')]
    .filter(el=>!el.disabled && (!el.media || matchMedia(el.media).matches)).every(el=>!!el.sheet);
  const challenge = /just a moment|access denied|verify you are human|checking your browser/i.test(document.title);
  return {url:location.href,ready:document.readyState==='complete' && !challenge,styles_ready:stylesReady,
    width:innerWidth,scroll_width:document.documentElement.scrollWidth,
    controls:controls.slice(0,12),ctas,form_submission_tested:false};
}
