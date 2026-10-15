(()=>{
 const panels=[...document.querySelectorAll('.masthead-search,.masthead-offers')];
 for(const panel of panels){
  panel.addEventListener('toggle',()=>{if(!panel.open)return;for(const other of panels)if(other!==panel)other.open=false;if(panel.matches('.masthead-search'))panel.querySelector('input[type=search]')?.focus();});
  panel.querySelector('.header-search-close')?.addEventListener('click',()=>{panel.open=false;panel.querySelector('summary').focus();});
  panel.addEventListener('keydown',e=>{if(e.key==='Escape'){panel.open=false;panel.querySelector('summary').focus();}});
 }
 document.addEventListener('click',e=>{for(const panel of panels)if(!panel.contains(e.target))panel.open=false;});
})();

(()=>{
 for(const nav of document.querySelectorAll('.local-tabs')){
  const wrap=document.createElement('div');wrap.className='topic-scroll';nav.before(wrap);wrap.append(nav);
  const make=(back)=>{const b=document.createElement('button');b.type='button';b.className='topic-scroll-button topic-scroll-'+(back?'back':'forward');b.setAttribute('aria-label',back?'Vorige onderwerpen':'Meer onderwerpen');b.hidden=true;b.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="'+(back?'m15 5-7 7 7 7':'m9 5 7 7-7 7')+'"/></svg>';wrap.append(b);b.addEventListener('click',()=>nav.scrollBy({left:(back?-1:1)*Math.max(140,nav.clientWidth*.7),behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}));return b;};
  const back=make(true),forward=make(false);
  const update=()=>{const hasBack=nav.scrollLeft>2;const hasForward=nav.scrollLeft+nav.clientWidth<nav.scrollWidth-2;back.hidden=!hasBack;forward.hidden=!hasForward;wrap.dataset.back=String(hasBack);wrap.dataset.forward=String(hasForward);};
  nav.addEventListener('scroll',update,{passive:true});new ResizeObserver(update).observe(nav);
  nav.addEventListener('focusin',e=>{if(e.target.matches('a'))e.target.scrollIntoView({block:'nearest',inline:'nearest'});});
  document.fonts?.ready.then(update);addEventListener('load',update);update();
 }
})();

(()=>{const refresh=async()=>{if(document.hidden)return;try{const r=await fetch('/api/weather',{cache:'no-store'});if(!r.ok)return;const d=await r.json();const current=document.querySelector('.masthead-weather');if(current&&d.html){const t=document.createElement('template');t.innerHTML=d.html;current.replaceWith(t.content.firstElementChild);}}catch{}};setInterval(refresh,600000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});})();
