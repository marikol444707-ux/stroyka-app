import {normalizeProjectContext} from './project-context.js';
import {planGeometry} from './family-plan-geometry.js';
// Zones explain the existing sketch. They do not alter or allocate rooms.
export const planZones=[
 {id:'living',bounds:[0,-1.235,6.85,4.85],label:[3.45,2.25]},
 {id:'hall',bounds:[-1.735,-4.85,0,4.85],label:[-.85,.15]},
 {id:'bedroom1',bounds:[-6.85,1.615,-1.865,4.85],label:[-4.45,3.15]},
 {id:'bedroom2',bounds:[-6.85,-1.485,-1.865,1.485],label:[-4.45,0]},
 {id:'bedroom3',bounds:[-6.85,-4.85,-1.865,-1.615],label:[-4.45,-3.15]},
 {id:'bath',bounds:[0,-4.85,2.535,-1.365],label:[1.3,-3.15]},
 {id:'utility',bounds:[2.665,-4.85,4.535,-1.365],label:[3.6,-3.15]},
 {id:'office',bounds:[4.665,-4.85,6.85,-1.365],label:[5.75,-3.15]}
];
const questions={living:'Обсудим расположение кухни, обеденного места и проход на террасу.',hall:'Проверим ширину проходов и маршруты между комнатами.',bedroom1:'Обсудим, кому нужна эта спальня, хранение и расположение кровати.',bedroom2:'Обсудим назначение комнаты: детская, гостевая или другая задача семьи.',bedroom3:'Обсудим назначение комнаты и необходимую мебель.',bath:'Сейчас показан один санузел. Дополнительный потребует отдельной проработки.',utility:'Назначение оборудования, вентиляцию и требования к помещению проверит специалист.',office:'Кабинет уже показан отдельной комнатой. Рабочее место и хранение ещё можно обсудить.'};
export function familyPlan(value={}){
 const v=normalizeProjectContext(value),items=[];
 if(v.priorities.includes('office'))items.push({id:'office',state:'shown',title:'Отдельный кабинет',text:'Есть в эскизе. Проверим рабочее место и хранение.',room:'office'});
 if(v.priorities.includes('pantry'))items.push({id:'pantry',state:'discuss',title:'Кладовая',text:'Отдельная кладовая не выделена. Хозпомещение не назначаем кладовой без обсуждения.',room:'utility'});
 if(v.priorities.includes('bathroom'))items.push({id:'bathroom',state:'discuss',title:'Второй санузел',text:'В эскизе один санузел. Для второго потребуется проработка планировки и инженерии.',room:'bath'});
 if(v.priorities.includes('access'))items.push({id:'access',state:'discuss',title:'Вход без ступеней',text:'Один этаж не подтверждает доступность. Проверим вход, пороги, двери и проходы.',room:'hall'});
 return {family:v.adults||v.children?'Взрослые: '+(v.adults||'не указано')+' · дети: '+(v.children||'не указано'):'Расскажите о семье в форме выше',summary:'В эскизе три спальни и отдельный кабинет. Распределение комнат между членами семьи обсудим вместе.',items,rooms:planGeometry.rooms.map((r,i)=>({id:r.id,title:r.title,number:String(i+1).padStart(2,'0'),description:r.description,question:questions[r.id]})),geometryChanged:false,approved:false,recommendation:null};
}
