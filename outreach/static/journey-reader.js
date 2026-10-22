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
  const rgb = value => {
    const m=value.match(/^rgba?\(([^)]+)\)$/);if(!m)return null;
    const n=m[1].split(/[,\s/]+/).filter(Boolean).map(Number);
    return n.length>=3&&n.every(Number.isFinite)&&n.slice(0,3).every(v=>v>=0&&v<=255)&&
      (n.length===3||n[3]===1)?n.slice(0,3):null;
  };
  const luminance = values => values.map(v=>v/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4)
    .reduce((sum,v,i)=>sum+v*[0.2126,0.7152,0.0722][i],0);
  const contrast=[];let contrastChecked=0;
  for(const el of [...document.querySelectorAll('main p,main h1,main h2,main h3,body p,body h1,body h2,body h3')].slice(0,250)){
    if(!visible(el)||el.closest('nav,header,footer,aside,[role="dialog"],dialog,blockquote'))continue;
    const copy=[...el.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join(' ').trim().replace(/\s+/g,' ');
    if(copy.length<20)continue;
    const style=getComputedStyle(el),fg=rgb(style.color);if(!fg||style.textShadow!=='none')continue;
    let bg=null,uncertain=false;
    for(let node=el;node;node=node.parentElement){
      const s=getComputedStyle(node),color=s.backgroundColor;
      if(Number(s.opacity)!==1||s.backgroundImage!=='none'||s.filter!=='none'||s.mixBlendMode!=='normal') {uncertain=true;break;}
      for(const pseudo of ['::before','::after']){
        const p=getComputedStyle(node,pseudo);
        if(p.content!=='none'&&p.content!=='normal'&&p.display!=='none'&&
          (p.backgroundImage!=='none'||rgb(p.backgroundColor)))uncertain=true;
      }
      if(color!=='transparent'&&color!=='rgba(0, 0, 0, 0)'){
        const solid=rgb(color);if(!solid){uncertain=true;break;}if(!bg)bg=solid;
      }
    }
    if(uncertain||!bg)continue;
    const size=parseFloat(style.fontSize),weight=parseFloat(style.fontWeight);
    if(!Number.isFinite(size))continue;
    const minimum=size>=24||(size>=18.66&&weight>=700)?3:4.5;
    const a=luminance(fg),b=luminance(bg),ratio=(Math.max(a,b)+0.05)/(Math.min(a,b)+0.05);
    contrastChecked++;
    if(ratio<minimum)contrast.push({selector:selector(el),text:copy.slice(0,140),
      foreground:fg,background:bg,ratio:Number(ratio.toFixed(4)),minimum,font_size:size,font_weight:weight||400});
  }
  return {url:location.href,ready:document.readyState==='complete' && !challenge,styles_ready:stylesReady,
    width:innerWidth,scroll_width:document.documentElement.scrollWidth,
    controls:controls.slice(0,12),ctas,contrast:contrast.slice(0,6),contrast_checked:contrastChecked,
    form_submission_tested:false};
}
