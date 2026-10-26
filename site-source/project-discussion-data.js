import {materials} from './materials-data.js';
import {normalizeProjectContext,priorityNames,contactNames} from './project-context.js';
import {siteNames,discussionTopicNames} from './discussion-options.js';
const styleNames={warm:'Тёплый современный',minimal:'Светлый минимализм',classic:'Современная классика'};
export function projectDiscussion(choices={},context={},style='warm'){
 const v=normalizeProjectContext(context),items=['wall','roof','facade'].map(category=>{const m=materials.find(m=>m.category===category&&m.id===choices[category]);return {category,title:m?.title||'Пока не выбрано',materialId:m?.id||null};});
 const open=[];
 if(!v.adults||!v.children)open.push('Уточнить состав семьи и требования к помещениям.');
 if(!v.siteStatus)open.push('Уточнить, есть ли участок или его ещё нужно подобрать.');
 else if(v.siteStatus==='searching')open.push('Обсудить требования к участку и размещению дома при подборе.');
 if(!v.town)open.push('Уточнить населённый пункт будущего строительства.');
 const missing=items.filter(m=>!m.materialId).map(m=>({wall:'стены',roof:'покрытие кровли',facade:'отделку фасада'})[m.category]);if(missing.length)open.push('Обсудить открытые варианты: '+missing.join(', ')+'.');
 open.push('Проверить условия участка и возможность размещения дома.','Согласовать планировку, размеры и пожелания семьи.','Проверить полные составы конструкций, узлы и спецификации.','Уточнить состав работ и стоимость по актуальным расценкам.');
 return {family:v.adults||v.children?'Взрослые: '+(v.adults||'не указано')+' · дети: '+(v.children||'не указано'):'Пока не указана',priorities:v.priorities.map(k=>priorityNames[k]),site:siteNames[v.siteStatus]||'Пока не указано',town:v.town||'Пока не указан',channel:contactNames[v.channel]||'Пока не выбран',interior:styleNames[style]||'Оформление требует уточнения',items,topics:v.discussionTopics.map(k=>discussionTopicNames[k]),openQuestions:open,price:null,projectApproved:false,sent:false};
}
