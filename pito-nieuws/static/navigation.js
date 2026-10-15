/* Shared click navigation, including existing production login destinations. */
(()=>{
 const header=document.querySelector('.pito-navigation');
 if(!header)return;
 const nav=header.querySelector('nav'),toggle=header.querySelector('.pn-mobile-toggle'),shade=document.querySelector('.pn-backdrop');
 const buttons=[...header.querySelectorAll('.pn-trigger')];
 const compact=matchMedia('(max-width:1050px)');
 const panel=b=>document.getElementById(b.getAttribute('aria-controls'));
 function closePanels(){clearTimeout(leaveTimer);buttons.forEach(b=>{b.setAttribute('aria-expanded','false');delete b.dataset.openedBy;panel(b).hidden=true});shade.hidden=true;}
 function closeAll(){closePanels();nav.classList.remove('is-open');toggle.setAttribute('aria-expanded','false');toggle.querySelector('span').textContent='Menu';}
 let leaveTimer;
 function cancelLeave(){clearTimeout(leaveTimer);leaveTimer=null;}
 function show(b){clearTimeout(leaveTimer);closePanels();b.setAttribute('aria-expanded','true');b.dataset.openedBy='hover';panel(b).hidden=false;shade.hidden=compact.matches;}
 header.querySelectorAll('.pn-group').forEach(group=>{group.addEventListener('pointerenter',e=>{if(!compact.matches&&e.pointerType!=='touch'&&!group.classList.contains('pn-group--account'))show(group.querySelector('.pn-trigger'))});group.addEventListener('pointerleave',()=>{if(!compact.matches&&!group.classList.contains('pn-group--account'))leaveTimer=setTimeout(closePanels,250)});});
 buttons.forEach(b=>b.addEventListener('click',()=>{cancelLeave();const open=b.getAttribute('aria-expanded')==='true'&&b.dataset.openedBy!=='hover';closePanels();if(!open){b.setAttribute('aria-expanded','true');panel(b).hidden=false;shade.hidden=compact.matches;}}));
 toggle.addEventListener('click',()=>{const open=toggle.getAttribute('aria-expanded')==='true';closeAll();if(!open){nav.classList.add('is-open');toggle.setAttribute('aria-expanded','true');toggle.querySelector('span').textContent='Sluiten';}});
 document.addEventListener('click',e=>{if(!header.contains(e.target))closeAll();});
 document.addEventListener('keydown',e=>{if(e.key!=='Escape')return;const open=buttons.find(b=>b.getAttribute('aria-expanded')==='true');if(open){closePanels();open.focus();}else if(nav.classList.contains('is-open')){closeAll();toggle.focus();}});
 document.addEventListener('focusin',e=>{if(e.target!==document.body&&!header.contains(e.target))closeAll()});
 header.addEventListener('pointerenter',cancelLeave);
 nav.addEventListener('click',e=>{if(e.target.closest('a'))closeAll()});
 window.addEventListener('hashchange',()=>{closeAll();markCurrent()});
 compact.addEventListener('change',closeAll);
 function markCurrent(){
  const here=location.pathname+location.search+location.hash;
  nav.querySelectorAll('a').forEach(a=>{const u=new URL(a.href);const active=u.origin===location.origin&&u.pathname+u.search+u.hash===here;a.toggleAttribute('data-current',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  buttons.forEach(b=>{const group=b.closest('.pn-group');b.classList.toggle('is-current',!!group.querySelector('[data-current]'))});
 }
 markCurrent();
 const icons={
 aanbod:'<path d="M4 5h10l6 7-8 8-8-7Z"/><circle cx="8" cy="9" r="1"/>',
 werk:'<rect x="3" y="7" width="18" height="14" rx="3"/><path d="M8 7V4h8v3M3 12l9 3 9-3M12 13v4"/>',
 wijk:'<path d="m2 11 5-5 5 5m-9-1v9h8v-9m2-2 4-4 5 5m-8 0v10h7V9"/>',
 verhaal:'<path d="M12 20S2 14 2 8c0-5 7-6 10-1 3-5 10-4 10 1 0 6-10 12-10 12Z"/>',
 app:'<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 5h4M11 19h2"/>',
 live:'<path d="M19 9c0 6-7 12-7 12S5 15 5 9a7 7 0 1 1 14 0Z"/><circle cx="12" cy="9" r="2"/>',
 nieuws:'<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M7 8h10M7 12h4M7 16h4M15 12h2v4h-2Z"/>',
 missie:'<path d="m3 11 9-8 9 8M6 9v12h12V9M9 21v-7h6v7"/>'
 };
 header.querySelectorAll('[data-nav-icon]').forEach(el=>{const key=el.dataset.navIcon;if(window.pitoDetailAssets?.[key]){el.classList.add('pn-icon--3d');const img=document.createElement('img');img.src=window.pitoDetailAssets[key];img.alt='';el.append(img)}else el.innerHTML='<svg viewBox="0 0 24 24">'+(icons[key]||icons.missie)+'</svg>'});
})();
