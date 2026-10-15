// Remember an explicit municipality choice across news navigation and visits.
(() => {
 const key='pito-news-municipality', base='/nieuws/utrecht';
 const allowed=new Set(["", "amersfoort", "baarn", "bunnik", "bunschoten", "de-bilt", "de-ronde-venen", "eemnes", "houten", "ijsselstein", "leusden", "lopik", "montfoort", "nieuwegein", "oudewater", "renswoude", "rhenen", "soest", "stichtse-vecht", "utrecht", "utrechtse-heuvelrug", "veenendaal", "vijfheerenlanden", "wijk-bij-duurstede", "woerden", "woudenberg", "zeist"]);
 function saved(){try {const value=localStorage.getItem(key);return value!==null&&allowed.has(value)?value:null;}catch{return null;}}
 function remember(value){if(!allowed.has(value))return;try{localStorage.setItem(key,value);}catch{}updateLinks(value);}
 function updateLinks(value){
  const destination=base+(value?'/'+value:'');
  document.querySelectorAll('.news-brand-home,.masthead-main-nav a:first-child').forEach(a=>a.setAttribute('href',destination));
 }
 document.addEventListener('submit',event=>{
  const form=event.target;
  if(!(form instanceof HTMLFormElement)||!['/nieuws/kies','/nieuws/nuttige-adressen'].includes(new URL(form.action,location.href).pathname))return;
  const value=event.submitter?.name==='gemeente'?event.submitter.value:new FormData(form).get('gemeente');
  if(typeof value==='string')remember(value);
 },true);
 function restore(){
  const value=saved();if(value===null)return;
  updateLinks(value);
  if(value&&location.pathname.replace(/\/$/,'')===base){location.replace(base+'/'+value+location.search+location.hash);}
 }
 restore();window.addEventListener('pageshow',restore);
 window.addEventListener('storage',e=>{if(e.key===key){const value=saved();if(value!==null)updateLinks(value);}});
})();
document.querySelector('#municipality')?.addEventListener('change',e=>{try{localStorage.setItem('pito-news-municipality',e.target.value)}catch{}e.target.form.requestSubmit()});
for(const form of document.querySelectorAll('.editor form'))form.addEventListener('submit',async e=>{e.preventDefault();const b=form.querySelector('button');b.disabled=true;const msg=form.querySelector('[role=status]');try{const data=Object.fromEntries(new FormData(form));data.confirmed=form.querySelector('[name=confirmed]')?.checked||false;const response=await fetch(form.dataset.endpoint||'/api/news/review',{method:'POST',headers:{'Content-Type':'application/json','X-Pito-CSRF':document.querySelector('meta[name=csrf]').content},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error);msg.textContent=result.message;}catch(err){msg.textContent=err.message}finally{b.disabled=false}});

for(const form of document.querySelectorAll('form[data-endpoint="/api/community/submit"]')){
 const kind=form.querySelector('[name=kind]');
 const update=()=>{const story=kind.value==='story';form.querySelector('[data-community-story]').hidden=!story;form.querySelector('[data-community-join]').hidden=story;for(const name of ['title','summary','body','evidence'])form.querySelector('[name='+name+']').required=story;form.querySelector('[name=motivation]').required=!story;form.querySelector('button').textContent=story?'Bewaar verhaal voor beoordeling':'Bewaar aanmelding lokaal';};kind.addEventListener('change',update);update();
}
for(const tile of document.querySelectorAll('.drone-tile'))tile.addEventListener('click',()=>{const root=tile.closest('.utrecht-starter');root.querySelector('.drone-backdrop').style.backgroundImage='url(/news-static/images/'+tile.dataset.image+')';root.querySelector('.drone-backdrop').setAttribute('aria-label',tile.dataset.place+' vanuit de lucht, PITO-dronebeeld');root.querySelector('.drone-location').textContent=tile.dataset.place+' · '+tile.querySelector('small').textContent;for(const b of root.querySelectorAll('.drone-tile'))b.setAttribute('aria-pressed',String(b===tile));});

// Sharing stays on the visitor's device; no third-party trackers are loaded.
for(const button of document.querySelectorAll('[data-copy-link]'))button.addEventListener('click',async()=>{
 const status=button.parentElement.querySelector('.share-status');
 const url=document.querySelector('link[rel=canonical]')?.href||location.href;
 try{await navigator.clipboard.writeText(url);status.textContent='Link gekopieerd.'}catch{status.textContent='Kopieer de link uit de adresbalk.'}
});
for(const button of document.querySelectorAll('[data-share]')){
 if(navigator.share)button.hidden=false;
 button.addEventListener('click',async()=>{try{await navigator.share({title:document.title,url:document.querySelector('link[rel=canonical]')?.href||location.href})}catch{}});
}

// Preserve the current view and filters when changing municipality; keep submit as no-JS fallback.
for (const select of document.querySelectorAll('#starter-gemeente, #dossier-city')) {
 const form = select.form;
 if (!form) continue;
 for (const button of form.querySelectorAll('button')) button.hidden = true;
 select.addEventListener('change', () => form.requestSubmit());
}

// Municipality selection is a full navigation, not a partial content update.
for (const picker of document.querySelectorAll('.municipality-picker')) {
 document.addEventListener('pointerdown',e=>{if(picker.open&&!picker.contains(e.target))picker.open=false;});
 document.addEventListener('focusin',e=>{if(picker.open&&!picker.contains(e.target))picker.open=false;});
 const search = picker.querySelector('.municipality-search');
 const choices = [...picker.querySelectorAll('.municipality-grid button')];
 const reset = () => { if(search) search.value=''; choices.forEach(b=>b.hidden=false); picker.querySelector('.municipality-empty').hidden=true; };
 picker.addEventListener('toggle',()=>{if(picker.open){search?.focus({preventScroll:true});picker.querySelector('.municipality-grid')?.scrollTo(0,0);}else reset();});
 search?.addEventListener('input',()=>{const q=search.value.trim().toLocaleLowerCase('nl');picker.querySelector('.municipality-grid')?.scrollTo(0,0);choices.forEach(b=>b.hidden=!b.textContent.toLocaleLowerCase('nl').includes(q));picker.querySelector('.municipality-empty').hidden=choices.some(b=>!b.hidden);});
 picker.querySelector('.municipality-close')?.addEventListener('click',()=>{picker.open=false;picker.querySelector('summary').focus();});
 picker.addEventListener('keydown',e=>{if(e.key==='Escape'){picker.open=false;picker.querySelector('summary').focus();}if(e.key==='Enter'&&e.target===search){e.preventDefault();const visible=choices.filter(b=>!b.hidden);if(visible.length===1)visible[0].click();}});
}

// Let the full editorial card activate its primary link. Keep real links,
// controls, text selection and modified clicks working as expected.
(() => {
 const cards='.story,.latest-row,.environment-row,.weekly-feature,.tips-row>article,.inline-related,.home-agenda-columns li,.topic-more li,.news-latest .timeline li,.article-latest-timeline li,.app-agenda-card,.agenda-item,.listing';
 function activate(event){
  if(event.defaultPrevented || (event.type==='click' && event.button!==0) || (event.type==='auxclick' && event.button!==1))return;
  const target=event.target instanceof Element?event.target:null;
  if(!target || target.closest('a,button,input,select,textarea,summary,label,[contenteditable="true"]'))return;
  if(window.getSelection()?.toString().trim())return;
  const card=target.closest(cards);if(!card)return;
  const link=card.querySelector('h2 a[href],h3 a[href],.weekly-feature-link[href],.inline-related>div>a[href]') || card.querySelector('a[href]:not([aria-hidden="true"]):not(figcaption a)');
  if(!link)return;
  event.preventDefault();
  if(event.metaKey || event.ctrlKey || event.shiftKey || event.button===1){window.open(link.href,'_blank','noopener,noreferrer');return;}
  link.click();
 }
 document.addEventListener('click',activate);
 document.addEventListener('auxclick',activate);
})();
