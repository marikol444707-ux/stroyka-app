import {categories,materials,makeProjectBrief} from './materials-data.js';
const styleNames={warm:'Тёплый современный',minimal:'Светлый минимализм',classic:'Современная классика'};
export function createMaterialsUI({getStyle,onChoices,getContext=()=>null}){
  const $=s=>document.querySelector(s),root=$('#materials-panel'),choices={},comparisons={wall:new Set(),roof:new Set(),facade:new Set()},listeners=new Set();let category='wall',returnFocus=null,copyBusy=false;
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  function notify(message=''){$('#material-feedback').textContent=message;window.__MATERIALS_STATUS__={category,choices:{...choices},compare:[...comparisons[category]]};}
  function setBriefFeedback(text){for(const id of ['#brief-feedback','#discussion-copy-feedback']){const node=$(id);if(node&&node.textContent!==text)node.textContent=text;}}
  function setCopyBusy(value){copyBusy=value;for(const id of ['#copy-project-brief','#discussion-copy']){const node=$(id);if(node){node.setAttribute('aria-busy',String(value));node.setAttribute('aria-disabled',String(value));}}}
  function refreshBrief(){const next=makeProjectBrief(choices,styleNames[getStyle()]||styleNames.warm,getContext());if($('#project-brief').value!==next)setBriefFeedback(copyBusy?'Описание изменилось. После завершения скопируйте его ещё раз.':'');$('#project-brief').value=next;}
  function selectPreference(id,materialId){
    if(!categories[id]||(materialId!==null&&!materials.some(m=>m.category===id&&m.id===materialId)))return false;
    if(materialId===null)delete choices[id];else choices[id]=materialId;
    refreshBrief();onChoices({...choices});render();
    for(const listener of listeners)listener({...choices});
    notify('Пожелания обновлены. Конструкция дома ещё не утверждена.');return true;
  }
  function addFact(parent,label,text){const dt=el('dt',label),dd=el('dd',text);parent.append(dt,dd);}
  function renderComparison(){
    const list=materials.filter(m=>comparisons[category].has(m.id));
    root.querySelector('.comparison-toolbar').classList.toggle('has-selection',list.length>0);
    const button=$('#show-material-comparison');button.disabled=list.length<2;button.textContent='Сравнить выбранные ('+list.length+'/3)';
    const container=$('#material-comparison');container.replaceChildren();container.hidden=true;
    if(list.length<2)return;
    const table=el('table'),caption=el('caption','Сравнение для обсуждения · без рейтинга и неподтверждённых цен');table.append(caption);
    const thead=el('thead'),tr=el('tr');tr.append(el('th','Что сравниваем'));
    for(const m of list)tr.append(el('th',m.title));thead.append(tr);table.append(thead);
    const tbody=el('tbody');
    for(const [key,title] of [['benefit','Возможные преимущества'],['limitation','Ограничения'],['heat','Теплозащита'],['budget','Что влияет на смету']]){
      const row=el('tr');row.append(el('th',title));for(const m of list)row.append(el('td',m[key]));tbody.append(row);
    }table.append(tbody);container.append(table);
  }
  function render(){
    root.querySelector('[role=tabpanel]').setAttribute('aria-labelledby','category-'+category);
    for(const b of root.querySelectorAll('[data-material-category]')){const active=b.dataset.materialCategory===category;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;}
    const grid=$('#material-grid');grid.replaceChildren();
    for(const m of materials.filter(m=>m.category===category)){
      const card=el('article',undefined,'material-card');card.dataset.material=m.id;
      const swatch=el('div',undefined,'material-swatch '+m.texture);swatch.setAttribute('aria-hidden','true');card.append(swatch);
      card.append(el('small','Условная фактура · не образец поставщика','swatch-note'),el('h3',m.title),el('p',m.summary,'material-summary'));
      const facts=el('dl');addFact(facts,'Что может быть удобно',m.benefit);addFact(facts,'Что учитывать',m.limitation);card.append(facts);
      const details=el('details'),summary=el('summary','Тепло, бюджет и вопросы специалисту');details.append(summary);
      const more=el('dl');addFact(more,'Теплозащита',m.heat);addFact(more,'Что влияет на смету',m.budget);details.append(more);
      const ul=el('ul');for(const q of m.questions)ul.append(el('li',q));details.append(ul,el('small','Черновик пояснений. Характеристики и решение для участка должны проверить специалисты.','material-review'));card.append(details);
      const buttons=el('div',undefined,'material-actions');
      if(materials.filter(x=>x.category===category).length>1){
        const compare=el('button',comparisons[category].has(m.id)?'Убрать из сравнения':'Сравнить');compare.type='button';compare.dataset.compare=m.id;compare.setAttribute('aria-pressed',String(comparisons[category].has(m.id)));
        compare.addEventListener('click',()=>{
          const set=comparisons[category];if(set.has(m.id))set.delete(m.id);else if(set.size<3)set.add(m.id);else{notify('Можно сравнить до трёх вариантов. Сначала уберите один из выбранных.');return;}
          render();root.querySelector('[data-compare='+m.id+']')?.focus({preventScroll:true});notify();
        });buttons.append(compare);
      }
      const selected=choices[category]===m.id,discuss=el('button',selected?'Убрать из пожеланий':'Добавить к обсуждению');discuss.type='button';discuss.dataset.discuss=m.id;discuss.setAttribute('aria-pressed',String(selected));
      discuss.addEventListener('click',()=>{selectPreference(category,choices[category]===m.id?null:m.id);root.querySelector('[data-discuss='+m.id+']')?.focus({preventScroll:true});});buttons.append(discuss);card.append(buttons);grid.append(card);
    }renderComparison();notify();
  }
  function setCategory(id){if(!categories[id])return;category=id;render();}
  function open(id='wall'){returnFocus=document.activeElement;setCategory(id);root.dataset.view='catalogue';root.hidden=false;refreshBrief();$('#materials-heading').focus({preventScroll:true});root.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});}
  function close(){root.hidden=true;returnFocus?.focus({preventScroll:true});}
  $('#materials-close').addEventListener('click',close);
  $('#project-review-back').addEventListener('click',()=>open(category));
  root.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close();}});
  for(const b of root.querySelectorAll('[data-material-category]')){
    b.addEventListener('click',()=>setCategory(b.dataset.materialCategory));
    b.addEventListener('keydown',e=>{const keys=Object.keys(categories),i=keys.indexOf(category);let n;if(e.key==='ArrowRight')n=(i+1)%keys.length;else if(e.key==='ArrowLeft')n=(i+keys.length-1)%keys.length;else if(e.key==='Home')n=0;else if(e.key==='End')n=keys.length-1;else return;e.preventDefault();setCategory(keys[n]);root.querySelector('[data-material-category='+keys[n]+']').focus();});
  }
  $('#show-material-comparison').addEventListener('click',()=>{$('#material-comparison').hidden=false;$('#material-comparison').focus({preventScroll:true});$('#material-comparison').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});});
  $('#copy-project-brief').addEventListener('click',async()=>{
    if(copyBusy)return;refreshBrief();const text=$('#project-brief').value;setCopyBusy(true);setBriefFeedback('Копируем описание…');
    try{if(!navigator.clipboard?.writeText)throw Error('Clipboard unavailable');await navigator.clipboard.writeText(text);setBriefFeedback($('#project-brief').value===text?'Пожелания скопированы. Их можно вставить в сообщение выбранному вами специалисту.':'Выбор изменился во время копирования. Скопируйте обновлённые пожелания ещё раз.');}
    catch{$('#project-brief').focus();$('#project-brief').select();setBriefFeedback('Автоматически скопировать не удалось. Текст выделен — скопируйте его средствами устройства.');}
    finally{setCopyBusy(false);}
  });
  render();refreshBrief();
  function openBrief(){open(category);root.dataset.view='brief';$('#project-review-heading').focus({preventScroll:true});$('#project-review').scrollIntoView({block:'start',behavior:'instant'});}
  return {open,openBrief,hideForInspector:()=>{root.hidden=true;},refreshBrief,selectPreference,snapshot:()=>({...choices}),subscribe:listener=>{listeners.add(listener);return()=>listeners.delete(listener);}};
}
