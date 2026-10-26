import {siteNames,discussionTopicNames} from './discussion-options.js';
export const priorityNames={office:'Кабинет',pantry:'Кладовая',bathroom:'Второй санузел',access:'Удобство без ступеней'};
export const contactNames={call:'Телефон',telegram:'Telegram',whatsapp:'WhatsApp'};
const adults=new Set(['1','2','3','4+']),children=new Set(['0','1','2','3+']);
export function normalizeProjectContext(value={}){
 value=value&&typeof value==='object'?value:{};
 return {adults:adults.has(value.adults)?value.adults:'',children:children.has(value.children)?value.children:'',priorities:Object.keys(priorityNames).filter(k=>Array.isArray(value.priorities)&&value.priorities.includes(k)),note:Array.from(String(value.note||'').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g,'').trim()).slice(0,600).join(''),channel:Object.hasOwn(contactNames,value.channel)?value.channel:'',siteStatus:Object.hasOwn(siteNames,value.siteStatus)?value.siteStatus:'',town:Array.from(String(value.town||'').replace(/[\u0000-\u001f\u007f]/g,' ').trim()).slice(0,120).join(''),discussionTopics:Object.keys(discussionTopicNames).filter(k=>Array.isArray(value.discussionTopics)&&value.discussionTopics.includes(k))};
}
export function projectContextLines(value){
 const v=normalizeProjectContext(value),lines=[];
 if(v.adults||v.children)lines.push('Состав семьи заказчика: взрослых — '+(v.adults||'не указано')+', детей — '+(v.children||'не указано'));
 if(v.priorities.length)lines.push('Важно обсудить: '+v.priorities.map(k=>priorityNames[k]).join(', '));
 if(v.note)lines.push('Дополнительные пожелания: '+v.note);
 if(v.channel)lines.push('Предпочтительный способ связи: '+contactNames[v.channel]);
 if(v.siteStatus)lines.push('Участок: '+siteNames[v.siteStatus]);
 if(v.town)lines.push('Населённый пункт будущей стройки: '+v.town);
 if(v.discussionTopics.length)lines.push('Сначала хочу обсудить: '+v.discussionTopics.map(k=>discussionTopicNames[k]).join('; '));
 if(lines.length)lines.push('Пожелания семьи не меняют планировку автоматически; адаптацию эскиза нужно обсудить.');
 return lines;
}
export function createProjectContext(){
 let state=normalizeProjectContext();const listeners=new Set();
 const snapshot=()=>({...state,priorities:[...state.priorities],discussionTopics:[...state.discussionTopics]});
 function update(value){state=normalizeProjectContext({...state,...value});for(const f of listeners)f(snapshot());}
 return {snapshot,update,reset:()=>update({adults:'',children:'',priorities:[],note:'',channel:'',siteStatus:'',town:'',discussionTopics:[]}),subscribe:f=>{listeners.add(f);return()=>listeners.delete(f);}};
}
