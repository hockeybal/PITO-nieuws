(() => {
 const rows=document.querySelector('[data-latest-rows]');
 const pager=document.querySelector('[data-latest-pagination]');
 if(!rows || !pager)return;
 let busy=false;
 pager.addEventListener('click',async event=>{
  const link=event.target.closest('[data-latest-next]');
  if(!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;
  event.preventDefault();if(busy)return;busy=true;
  const status=document.querySelector('.latest-status');
  link.setAttribute('aria-disabled','true');status.textContent='Nieuws wordt geladen…';
  try {
   const response=await fetch(link.href);if(!response.ok)throw Error();
   const doc=new DOMParser().parseFromString(await response.text(),'text/html');
   const incoming=doc.querySelector('[data-latest-rows]');const next=doc.querySelector('[data-latest-pagination]');
   if(!incoming || !next)throw Error();
   const added=[...incoming.children];rows.append(...added);pager.replaceChildren(...next.childNodes);
   const first=added[0]?.querySelector('h2 a');first?.focus({preventScroll:true});
   status.textContent=added.length+' berichten toegevoegd.';
  } catch(error) {
   status.textContent='Laden lukt niet. Klik nogmaals om de volgende pagina te openen.';
   link.removeAttribute('data-latest-next');
  } finally {busy=false;link.removeAttribute('aria-disabled');}
 });
})();
