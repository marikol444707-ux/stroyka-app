import {projectDiscussion} from './project-discussion-data.js';
import {discussionTopicNames} from './discussion-options.js';
export function createProjectDiscussion({store,context,getStyle}){
 const root=document.querySelector('#discussion-preparation'),form=root.querySelector('#discussion-form'),$=s=>root.querySelector(s);let last='',current=null,renders=0;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 for(const [id,title] of Object.entries(discussionTopicNames)){const label=el('label'),input=el('input');input.type='checkbox';input.name='discussionTopic';input.value=id;label.append(input,el('span',title));$('#discussion-topics').append(label);}
 function render(){const v=context.snapshot(),next=projectDiscussion(store.snapshot(),v,getStyle()),key=JSON.stringify(next);if(key===last)return;last=key;current=next;renders++;
  for(const name of ['siteStatus','channel'])if(form.elements[name].value!==v[name])form.elements[name].value=v[name];if(document.activeElement!==form.elements.town&&form.elements.town.value!==v.town)form.elements.town.value=v.town;
  for(const input of form.querySelectorAll('input[name=discussionTopic]'))input.checked=v.discussionTopics.includes(input.value);
  const facts=$('#discussion-facts');facts.replaceChildren();for(const [label,value] of [['Семья',next.family],['Участок',next.site],['Населённый пункт',next.town],['Интерьер',next.interior],['Способ связи',next.channel]]){const row=el('div');row.append(el('dt',label),el('dd',value));facts.append(row);}
  $('#discussion-family-priorities').textContent=next.priorities.length?'Для семьи важно: '+next.priorities.join(', '):'Дополнительные пожелания семьи можно указать в начале страницы.';
  const host=$('#discussion-materials');host.replaceChildren();for(const item of next.items){const row=el('div');row.dataset.chosen=String(!!item.materialId);row.append(el('small',({wall:'Стены',roof:'Кровля',facade:'Фасад'})[item.category]),el('strong',item.title),el('span',item.materialId?'Пожелание для обсуждения':'Вопрос открыт'));host.append(row);}
  $('#discussion-open-questions').replaceChildren(...next.openQuestions.map(q=>el('li',q)));$('#discussion-open summary').textContent='Что ещё нужно обсудить · '+next.openQuestions.length;$('#discussion-priority-summary').textContent=next.topics.length?'Сначала обсудим: '+next.topics.join('; '):'Можно отметить несколько тем или оставить выбор открытым.';
 }
 function read(){context.update({siteStatus:form.elements.siteStatus.value,town:form.elements.town.value,channel:form.elements.channel.value,discussionTopics:[...form.querySelectorAll('input[name=discussionTopic]:checked')].map(i=>i.value)});$('#discussion-feedback').textContent='Описание обновлено. Сохраните выбор или скопируйте пожелания.';}
 form.addEventListener('input',read);form.addEventListener('change',read);form.addEventListener('submit',e=>{e.preventDefault();read();document.querySelector('#copy-project-brief').focus();});form.elements.town.addEventListener('blur',()=>{form.elements.town.value=context.snapshot().town;});
 $('#discussion-clear').addEventListener('click',()=>{context.update({siteStatus:'',town:'',discussionTopics:[],channel:''});$('#discussion-feedback').textContent='Эта форма очищена. Семья и выбранные материалы сохранены.';});
 $('#discussion-copy').addEventListener('click',()=>document.querySelector('#copy-project-brief').click());$('#discussion-show-text').addEventListener('click',()=>{const text=document.querySelector('#project-brief');text.scrollIntoView({block:'center',behavior:'instant'});text.focus({preventScroll:true});});
 context.subscribe(()=>{store.refreshBrief();render();});store.subscribe(render);render();return {render,audit:()=>({...projectDiscussion(store.snapshot(),context.snapshot(),getStyle()),renders})};
}
