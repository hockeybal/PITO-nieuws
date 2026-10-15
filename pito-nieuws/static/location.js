/* Geometry stays on-device. No coordinates, accuracy or location telemetry are sent. */
function pitoInsideRing(point,ring){
 let inside=false;const [x,y]=point;
 for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const [xi,yi]=ring[i], [xj,yj]=ring[j];
  if((yi>y)!==(yj>y) && x<(xj-xi)*(y-yi)/(yj-yi)+xi)inside=!inside;
 }
 return inside;
}
function pitoMunicipality(point,features){
 for(const feature of features){
  const polygons=feature.geometry.type==='Polygon'?[feature.geometry.coordinates]:feature.geometry.coordinates;
  if(polygons.some(rings=>pitoInsideRing(point,rings[0])&&!rings.slice(1).some(r=>pitoInsideRing(point,r))))return feature.properties.slug;
 }
 return '';
}
(() => {
 if(typeof document==='undefined')return;
 const dialog=document.querySelector('.location-dialog');if(!dialog)return;
 const use=dialog.querySelector('[data-location-use]'),status=dialog.querySelector('.location-status');
 let attempt=0,sourcePicker=null;
 function open(picker){sourcePicker=picker;status.textContent='';use.disabled=false;dialog.showModal();}
 function close(){attempt++;dialog.close();use.disabled=false;}
 document.querySelectorAll('[data-location-open]').forEach(b=>b.addEventListener('click',()=>open(b.closest('.municipality-picker'))));
 dialog.querySelector('[data-location-close]').addEventListener('click',close);
 dialog.addEventListener('cancel',()=>{attempt++;use.disabled=false;});
 dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close();}});
 dialog.querySelector('[data-location-manual]').addEventListener('click',()=>{
  close();const picker=sourcePicker||document.querySelector('.municipality-picker');
  if(picker){picker.open=true;picker.querySelector('.municipality-search')?.focus();}
 });
 use.addEventListener('click',()=>{
  if(!navigator.geolocation){status.textContent='Je browser ondersteunt dit niet. Kies hieronder zelf je gemeente.';return;}
  const run=++attempt;use.disabled=true;status.textContent='Je locatie bepalen…';
  navigator.geolocation.getCurrentPosition(async position=>{
   if(run!==attempt||!dialog.open)return;
   try{
    const {longitude,latitude,accuracy}=position.coords;
    if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||!Number.isFinite(accuracy)||accuracy>2000)throw Error('accuracy');
    const response=await fetch('/news-static/utrecht-boundaries.json');if(!response.ok)throw Error('data');
    const data=await response.json();if(data.features?.length!==26)throw Error('data');
    const slug=pitoMunicipality([longitude,latitude],data.features);
    if(run!==attempt||!dialog.open)return;
    // Reuse the existing selection submission to preserve agenda/topic context.
    const picker=sourcePicker||document.querySelector('.municipality-picker');
    const choice=[...(picker?.querySelectorAll('.municipality-grid button')||[])].find(b=>b.value===slug);
    try{localStorage.setItem('pito-news-municipality',slug)}catch{}
    if(choice){choice.click();return;}
    location.assign('/nieuws/utrecht'+(slug?'/'+encodeURIComponent(slug):''));
   }catch(error){if(run!==attempt)return;use.disabled=false;status.textContent=error.message==='accuracy'?'Je locatie is niet nauwkeurig genoeg. Probeer opnieuw of kies zelf je gemeente.':'De gemeente kon niet worden bepaald. Probeer opnieuw of kies zelf.';}
  },error=>{
   if(run!==attempt)return;use.disabled=false;
   status.textContent=error.code===1?'Geen toegang tot je locatie. Je kunt zelf een gemeente kiezen.':'Je locatie is niet beschikbaar. Probeer opnieuw of kies zelf je gemeente.';
  },{enableHighAccuracy:true,timeout:12000,maximumAge:60000});
 });
 // Location selection opens only after the visitor chooses the location button.
})();
