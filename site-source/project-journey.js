import {materials} from './materials-data.js';

// Derive every label from the existing preference store. A visited step is not
// a material choice and a material choice is not an approved construction.
export function createProjectJourney({store,onChoose,onBrief}){
  const root=document.querySelector('#project-path');
  const review=document.querySelector('#project-review');
  const names={wall:'Стены',roof:'Покрытие кровли',facade:'Отделка фасада'};
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  const resolve=(choices,key)=>materials.find(m=>m.id===choices[key]&&m.category===key);
  function render(){
    const choices=store.snapshot();
    for(const key of ['wall','roof','facade']){
      const item=resolve(choices,key),step=root.querySelector('[data-project-step="'+key+'"]');
      step.querySelector('small').textContent=item?item.title:'Пока не выбрано';
      step.dataset.chosen=String(!!item);
      step.setAttribute('aria-label',names[key]+': '+(item?item.title+' — изменить пожелание':'выбрать материал'));
    }
    const count=['wall','roof','facade'].filter(key=>resolve(choices,key)).length;
    root.querySelector('#project-path-status').textContent=count===3?'Стены, кровля и фасад добавлены к обсуждению':count?'Выбрано пожеланий: '+count+' из трёх':'Начните со стен, кровли или фасада';
    root.querySelector('#project-path-count').textContent=count+' / 3';
    root.querySelector('[data-project-step="brief"] small').textContent=count===3?'Проверить и скопировать':'Можно обсудить и без полного выбора';
    const host=review.querySelector('#project-review-cards'),focused=document.activeElement;
    const focusKey=host.contains(focused)?focused.dataset.reviewEdit||focused.dataset.reviewRemove:null;
    const focusAction=focused?.hasAttribute('data-review-remove')?'remove':'edit';
    host.replaceChildren();
    for(const key of Object.keys(names)){
      const item=resolve(choices,key),card=node('article',null,'project-review-card');
      card.append(node('small',names[key]),node('h4',item?item.title:'Ещё не выбрано'));
      if(item){
        const facts=node('dl');
        for(const [label,value] of [['Что может подойти',item.benefit],['Что учесть',item.limitation]])facts.append(node('dt',label),node('dd',value));
        card.append(node('span','Пожелание для обсуждения','project-choice-badge'),facts);
        const details=node('details');details.append(node('summary','Вопросы специалисту'));
        const list=node('ul');for(const q of item.questions)list.append(node('li',q));details.append(list);card.append(details);
      }else card.append(node('p',key==='facade'?'Фасад можно обсудить отдельно.':'Можно оставить решение открытым и обсудить его со специалистом.'));
      const actions=node('div',null,'project-review-actions'),edit=node('button',item?'Изменить':'Посмотреть варианты');
      edit.type='button';edit.dataset.reviewEdit=key;edit.setAttribute('aria-label',(item?'Изменить: ':'Выбрать: ')+names[key]);edit.addEventListener('click',()=>onChoose(key));actions.append(edit);
      if(item){const remove=node('button','Убрать');remove.type='button';remove.dataset.reviewRemove=key;remove.setAttribute('aria-label','Убрать из пожеланий: '+names[key]);remove.addEventListener('click',()=>store.selectPreference(key,null));actions.append(remove);}
      card.append(actions);host.append(card);
    }
    if(focusKey){const target=host.querySelector('[data-review-'+focusAction+'="'+focusKey+'"]')||host.querySelector('[data-review-edit="'+focusKey+'"]');target?.focus({preventScroll:true});}
  }
  for(const step of root.querySelectorAll('[data-project-step]'))step.addEventListener('click',()=>step.dataset.projectStep==='brief'?onBrief():onChoose(step.dataset.projectStep));
  store.subscribe(render);render();
  return {render};
}
