(() => {
 const reduce=matchMedia('(prefers-reduced-motion: reduce)');
 const videos=[...document.querySelectorAll('[data-campaign-video]')];
 const pending=new WeakSet();
 const update=v=>{const b=v.parentElement.querySelector('button');b.innerHTML=v.paused?'<span aria-hidden="true">▶</span>':'<span aria-hidden="true">Ⅱ</span>';b.title=v.paused?'Video afspelen':'Video pauzeren';b.setAttribute('aria-label',v.paused?'Video afspelen':'Video pauzeren');};
 const visible=v=>{const r=v.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight;};
 const play=v=>{if(!v.paused||pending.has(v))return;pending.add(v);const result=v.play();if(result)result.catch(()=>update(v)).finally(()=>pending.delete(v));else pending.delete(v);};
 const sync=()=>videos.forEach(v=>{if(visible(v)&&!reduce.matches&&!v.dataset.userPaused&&!document.hidden){play(v);}else if(!v.paused)v.pause();});
 const observer=new IntersectionObserver(sync,{threshold:[0,.05]});
 videos.forEach(v=>{
  v.muted=true;v.defaultMuted=true;v.playsInline=true;v.setAttribute('webkit-playsinline','');
  // One complete story. Never seek or reload when scrolling or resizing.
  v.load();
  v.addEventListener('playing',()=>update(v));v.addEventListener('pause',()=>update(v));v.addEventListener('canplay',sync);observer.observe(v);
  v.parentElement.querySelector('button').addEventListener('click',()=>{if(v.paused){delete v.dataset.userPaused;play(v);}else{v.dataset.userPaused='1';v.pause();}});
 });
 document.addEventListener('visibilitychange',sync);reduce.addEventListener('change',sync);addEventListener('resize',sync);addEventListener('pageshow',sync);sync();
 const align=()=>{const banner=document.querySelector('.local-tabs');if(!banner)return;const top=banner.getBoundingClientRect().bottom+scrollY;document.documentElement.style.setProperty('--pito-campaign-top',top+'px');const wings=document.querySelector('.segmented-wings'),main=document.querySelector('main');if(wings&&main)wings.style.maxHeight=Math.max(0,main.getBoundingClientRect().bottom+scrollY-top-40)+'px';};
 addEventListener('resize',align);addEventListener('load',align);if(document.fonts)document.fonts.ready.then(align);const banner=document.querySelector('.local-tabs');if(banner)new ResizeObserver(align).observe(banner);align();
})();
