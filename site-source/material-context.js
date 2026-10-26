import {materialContext} from './material-context-data.js';
export function createMaterialContext({getChoices,onView,onChoose,onCompare,onBrief,onEngage}){
 const root=document.querySelector('#material-context'),$=s=>root.querySelector(s),abort=new AbortController(),options={signal:abort.signal};let view={loaded:false},suspended=false,last='',current=materialContext(),renders=0;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 function engage(){if(!root.hidden&&current.visible)onEngage();}
 function update(){
  const next=materialContext({...view,suspended,choices:getChoices()}),key=JSON.stringify(next);if(key===last)return;last=key;const resetDetails=next.category!==current.category||next.materialId!==current.materialId||next.state!==current.state;current=next;root.hidden=!next.visible;
  if(!next.visible)return;renders++;root.dataset.category=next.category;root.dataset.state=next.state;
  for(const b of root.querySelectorAll('[data-context-view]'))b.setAttribute('aria-pressed',String(b.dataset.contextView===next.category));
  $('#context-status').textContent=next.status;$('#context-status').dataset.state=next.state;$('#context-title').textContent=next.title;$('#context-scope').textContent=next.scope;
  const related=$('#context-related');related.hidden=!next.related;related.textContent=next.related||'';
  const facts=$('#context-facts');facts.replaceChildren();for(const row of next.facts){const box=el('div');box.append(el('dt',row.label),el('dd',row.text));facts.append(box);}facts.hidden=!next.facts.length;
  $('#context-empty').hidden=next.facts.length>0;$('#context-empty').textContent=next.state==='unresolved'?'Выбор основы стены или покрытия кровли не определяет этот слой. Его решение нужно согласовать отдельно.':'Откройте варианты, чтобы сравнить преимущества и ограничения. Просмотр сам по себе не добавляет материал в пожелания.';
  const details=$('#context-details');details.hidden=!next.budget&&!next.questions.length;if(resetDetails)details.open=false;
  $('#context-budget').hidden=!next.budget;$('#context-budget-text').textContent=next.budget||'';$('#context-questions').replaceChildren(...next.questions.map(q=>el('li',q)));
  const names={wall:'стены',roof:'покрытие',facade:'отделку'};$('#context-choose').textContent=(next.choiceId?'Изменить ':'Выбрать ')+names[next.category];
 }
 root.addEventListener('pointerdown',engage,{...options,capture:true});root.addEventListener('focusin',engage,options);
 for(const b of root.querySelectorAll('[data-context-view]'))b.addEventListener('click',()=>{if(current.visible){engage();onView(b.dataset.contextView);}},options);
 $('#context-choose').addEventListener('click',()=>{if(current.visible)onChoose(current.category);},options);$('#context-compare').addEventListener('click',()=>{if(current.visible)onCompare(current.category);},options);$('#context-brief').addEventListener('click',()=>{if(current.visible)onBrief();},options);
 function setView(value){view={...value};update();}
 function setSuspended(value){if(suspended===!!value)return;suspended=!!value;update();}
 update();return {setView,setSuspended,refresh:update,audit:()=>({...current,facts:current.facts.map(f=>({...f})),questions:[...current.questions],renders}),dispose(){abort.abort();root.hidden=true;}};
}
