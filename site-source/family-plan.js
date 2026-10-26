import {familyPlan,planZones} from './family-plan-data.js';
import {planGeometry} from './family-plan-geometry.js';
export function createFamilyPlan({context,onEnter,onBrief}){
 const root=document.querySelector('#family-plan'),$=s=>root.querySelector(s),ns='http://www.w3.org/2000/svg';let selected='living',busy=false,alive=true,last='';
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const svg=(tag,attrs={})=>{const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);return n;};
 const xy=([x,z])=>[(x+8)*40,(z+5.8)*40];
 const drawing=$('#family-plan-drawing');
 const zones=svg('g'),details=svg('g',{'pointer-events':'none'}),numbers=svg('g',{'pointer-events':'none'});drawing.append(zones,details,numbers);
 // Actual wall/furniture polygons from the same model's navigation export.
 for(const z of planZones){const [x1,y1]=xy(z.bounds.slice(0,2)),[x2,y2]=xy(z.bounds.slice(2));zones.append(svg('rect',{x:x1,y:y1,width:x2-x1,height:y2-y1,'data-plan-region':z.id,rx:2}));}
 for(const c of [...planGeometry.furniture,...planGeometry.walls]){const p=svg('polygon',{points:c.polygon.map(p=>xy(p).join(',')).join(' '),class:c.group==='03_walls'?(c.name.includes('glass')?'plan-glass':c.name.includes('door')?'plan-door':'plan-wall'):'plan-furniture'});details.append(p);}
 const model=familyPlan(context.snapshot());
 for(const room of model.rooms){const zone=planZones.find(z=>z.id===room.id),[cx,cy]=xy(zone.label),g=svg('g',{'data-plan-number':room.id});g.append(svg('circle',{cx,cy,r:16}));const t=svg('text',{x:cx,y:cy+4,'text-anchor':'middle'});t.textContent=room.number;g.append(t);numbers.append(g);const b=el('button');b.type='button';b.dataset.planRoom=room.id;b.setAttribute('aria-controls','family-plan-detail');b.append(el('small',room.number),el('span',room.title));b.addEventListener('click',()=>select(room.id));$('#family-plan-list').append(b);}
 drawing.addEventListener('click',e=>{const id=e.target.closest('[data-plan-region]')?.dataset.planRegion;if(id)select(id);});
 function select(id){if(!model.rooms.some(r=>r.id===id))return;selected=id;render();}
 function render(){const data=familyPlan(context.snapshot()),signature=JSON.stringify([data,selected,busy]);if(signature===last)return;last=signature;
  $('#plan-family').textContent=data.family;$('#plan-family-summary').textContent=data.summary;
  const room=data.rooms.find(r=>r.id===selected);$('#plan-selected-number').textContent='КОМНАТА '+room.number;$('#plan-selected-title').textContent=room.title;$('#plan-selected-description').textContent=room.description;$('#plan-selected-question').textContent=room.question;
  const enter=$('#plan-enter');enter.textContent=busy?'Открываем 3D…':'Заглянуть: '+room.title;enter.disabled=busy;enter.setAttribute('aria-busy',String(busy));
  for(const b of root.querySelectorAll('[data-plan-room]'))b.setAttribute('aria-pressed',String(b.dataset.planRoom===selected));for(const r of root.querySelectorAll('[data-plan-region],[data-plan-number]'))r.dataset.selected=String((r.dataset.planRegion||r.dataset.planNumber)===selected);
  const host=$('#plan-family-findings');host.replaceChildren();if(!data.items.length){const p=el('p','Отметьте важные помещения в форме выше — здесь покажем, что есть в эскизе и что требует изменений.');host.append(p);}for(const item of data.items){const row=el('div');row.dataset.state=item.state;row.append(el('small',item.state==='shown'?'ЕСТЬ В ЭСКИЗЕ':'НУЖНО ОБСУДИТЬ'),el('h4',item.title),el('p',item.text));const b=el('button','Посмотреть место на плане');b.type='button';b.addEventListener('click',()=>{select(item.room);$('#family-plan-detail').scrollIntoView({block:'center',behavior:'instant'});$('#plan-selected-title').focus({preventScroll:true});});row.append(b);host.append(row);}
 }
 $('#plan-enter').addEventListener('click',async()=>{if(busy)return;const target=selected;busy=true;render();$('#plan-open-feedback').textContent='Открываем выбранную комнату…';try{const opened=await onEnter(target);if(alive)$('#plan-open-feedback').textContent=opened?'В 3D открыта: '+model.rooms.find(r=>r.id===target).title+'. Вернуться можно кнопкой «К обзору комнат».':'3D пока недоступно. План и пожелания можно изучать без модели.';}catch{if(alive)$('#plan-open-feedback').textContent='Не удалось открыть 3D. План и пожелания доступны здесь.';}finally{busy=false;if(alive)render();}});
 $('#plan-discuss').addEventListener('click',()=>{const v=context.snapshot();context.update({discussionTopics:[...v.discussionTopics,'layout']});onBrief();});
 context.subscribe(render);render();return {select,render,audit:()=>({...familyPlan(context.snapshot()),selected,busy,modelSha256:planGeometry.modelSha256})};
}
