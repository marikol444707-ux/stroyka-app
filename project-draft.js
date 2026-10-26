import {normalizeProjectContext} from './project-context.js';
import {materials} from './materials-data.js';
export const draftKey='stroyka:house-01:project-draft:v1';
const styles=new Set(['warm','minimal','classic']);
export function normalizeDraft(raw){
 if(!raw||raw.version!==1||raw.project!=='house-01'||!raw.context||typeof raw.context!=='object'||Array.isArray(raw.context)||!raw.choices||typeof raw.choices!=='object'||Array.isArray(raw.choices)||!styles.has(raw.style))throw Error('INCOMPATIBLE_DRAFT');
 const choices={};for(const category of ['wall','roof','facade']){const id=raw.choices?.[category];if(id!=null){if(!materials.some(m=>m.category===category&&m.id===id))throw Error('UNKNOWN_MATERIAL');choices[category]=id;}}
 return {version:1,project:'house-01',context:normalizeProjectContext(raw.context),choices,style:raw.style};
}
export function draftRepository(storage){return{
 save(value){const clean=normalizeDraft(value);storage.setItem(draftKey,JSON.stringify(clean));return clean;},
 load(){const text=storage.getItem(draftKey);if(text===null)return null;if(text.length>32000)throw Error('DRAFT_TOO_LARGE');return normalizeDraft(JSON.parse(text));},
 remove(){storage.removeItem(draftKey);}
};}
export function createProjectDraft({context,store,getStyle,setStyle}){
 const host=document.querySelector('#project-draft'),status=host.querySelector('[role=status]');
 const report=t=>{if(status.textContent!==t)status.textContent=t;};
 function repository(){return draftRepository(window.localStorage);}
 host.querySelector('[data-draft=save]').addEventListener('click',()=>{try{repository().save({version:1,project:'house-01',context:context.snapshot(),choices:store.snapshot(),style:getStyle()});report('Выбор сохранён на этом устройстве. После изменений сохраните его ещё раз.');}catch{report('Не удалось сохранить выбор. Можно скачать описание или скопировать его ниже.');}});
 host.querySelector('[data-draft=restore]').addEventListener('click',()=>{try{const saved=repository().load();if(!saved){report('Сохранённого выбора на этом устройстве нет.');return;}setStyle(saved.style);for(const category of ['wall','roof','facade'])store.selectPreference(category,saved.choices[category]||null);context.update(saved.context);report('Сохранённый выбор восстановлен. Проверьте пожелания ниже.');}catch{report('Черновик недоступен или несовместим. Текущий выбор не изменён.');}});
 host.querySelector('[data-draft=delete]').addEventListener('click',()=>{try{repository().remove();report('Черновик удалён с этого устройства. Текущий выбор на странице оставлен.');}catch{report('Не удалось удалить черновик. Проверьте настройки хранения данных браузера.');}});
 host.querySelector('[data-draft=download]').addEventListener('click',()=>{store.refreshBrief();const blob=new Blob([document.querySelector('#project-brief').value],{type:'text/plain;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='СтройКа-Дом-01-пожелания.txt';link.click();setTimeout(()=>URL.revokeObjectURL(url),30000);report('Описание подготовлено для скачивания. Обращение в компанию не отправлено.');});
 const edited=()=>{report('Выбор изменён. Нажмите «Сохранить выбор», чтобы обновить черновик.');};context.subscribe(edited);store.subscribe(edited);
 try{if(repository().load())report('На этом устройстве есть сохранённый выбор. Можно восстановить его или сохранить текущий.');}catch{report('Сохранённый черновик недоступен. Можно продолжить без него.');}
}
