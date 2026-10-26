import {materials} from './materials-data.js';
import {projectContextLines} from './project-context.js';
const styleNames={warm:'Тёплый современный',minimal:'Светлый минимализм',classic:'Современная классика'};
export function createPublicSite({store,context,onExplore,onChoose,onBrief,getStyle}){
 const $=s=>document.querySelector(s),form=$('#family-form');let busy=false;
 const scroll=el=>el.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
 function render(){
  const choices=store.snapshot(),v=context.snapshot();let count=0;
  if(form.elements.channel.value!==v.channel)form.elements.channel.value=v.channel;
  for(const key of ['wall','roof','facade']){const m=materials.find(x=>x.id===choices[key]&&x.category===key);if(m)count++;$('[data-public-choose="'+key+'"]').textContent=m?'Изменить':'Выбрать';$('[data-public-material="'+key+'"]').textContent=m?m.title:'Решение открыто';}
  $('#public-choice-count').textContent=count+' / 3';$('#mobile-choice-count').textContent=count?'Выбрано решений: '+count:'Дом 01 · ваш выбор';
  $('#public-style-name').textContent=styleNames[getStyle()];
  $('#family-summary').textContent=v.adults||v.children?'Взрослые: '+(v.adults||'не указано')+' · дети: '+(v.children||'не указано'):'Расскажите, для кого выбираете дом';
  const host=$('#public-family-notes');host.replaceChildren();
  for(const text of projectContextLines(v).filter(x=>!x.startsWith('Пожелания семьи'))){const li=document.createElement('li');li.textContent=text;host.append(li);}
  if(!host.children.length){const li=document.createElement('li');li.textContent='Состав семьи и пожелания можно добавить выше.';host.append(li);}
 }
 function readForm(){return {adults:form.elements.adults.value,children:form.elements.children.value,channel:form.elements.channel.value,note:form.elements.note.value,priorities:[...form.querySelectorAll('input[name=priority]:checked')].map(x=>x.value)};}
 form.addEventListener('input',()=>context.update(readForm()));form.addEventListener('change',()=>context.update(readForm()));form.addEventListener('submit',e=>{e.preventDefault();onBrief();});
 $('#family-reset').addEventListener('click',()=>{form.reset();context.update({adults:'',children:'',priorities:[],note:''});$('#family-feedback').textContent='Пожелания семьи очищены. Участок, способ связи и выбранные материалы сохранены.';});
 context.subscribe(()=>{store.refreshBrief();$('#family-feedback').textContent='Пожелания добавлены к описанию для обсуждения.';render();});store.subscribe(render);
 for(const b of document.querySelectorAll('[data-explore]'))b.addEventListener('click',async()=>{
  if(busy)return;busy=true;document.querySelectorAll('[data-explore]').forEach(x=>x.disabled=true);$('#public-experience-feedback').textContent='Открываем дом…';scroll($('#house-experience'));
  try{const opened=await onExplore(b.dataset.explore);$('#public-experience-feedback').textContent=opened?'Дом открыт. Выберите ракурс или материал.':'Не удалось открыть 3D. Пожелания и сравнение материалов доступны ниже.';}
  catch{$('#public-experience-feedback').textContent='Не удалось открыть 3D. Можно продолжить выбор материалов без модели.';}
  finally{busy=false;document.querySelectorAll('[data-explore]').forEach(x=>x.disabled=false);}
 });
 for(const b of document.querySelectorAll('[data-public-choose]'))b.addEventListener('click',()=>onChoose(b.dataset.publicChoose));
 for(const b of document.querySelectorAll('[data-open-brief]'))b.addEventListener('click',onBrief);
 for(const a of document.querySelectorAll('a[data-scroll]'))a.addEventListener('click',e=>{const el=document.querySelector(a.hash);if(el){e.preventDefault();scroll(el);el.focus({preventScroll:true});}});
 render();return {render};
}
