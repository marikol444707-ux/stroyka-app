import {materials} from './materials-data.js';
import {assemblySteps} from './assembly-motion.js';
const visibleModes=new Set(['assembled','terrace','roof','facade','wall','wall-section','exploded']);
const roleInfo={
 '16_roof_battens':{category:'roof',title:'Обрешётка',scope:'Показана опора покрытия в учебной модели. Её материал, шаг, сечения и крепления ещё не выбраны.'},
 '15_roof_underlay':{category:'roof',title:'Подкровельный слой',scope:'Показано место слоя под покрытием. Тип защиты, вентиляция и примыкания ещё не согласованы.'},
 '14_rafters':{category:'roof',title:'Стропильная система',scope:'Показаны несущие элементы кровли. Материал, сечения, шаг и соединения требуют расчёта.'},
 '04_ceiling':{category:'roof',title:'Перекрытие',scope:'Показан слой над помещениями. Полный состав, нагрузки и узлы ещё не утверждены.'},
 '10_insulation':{category:'wall',title:'Теплоизоляция',scope:'Место утепления в учебном фрагменте не означает выбор утеплителя. Тип, толщина и необходимость определяются расчётом всей стены.'},
 '11_vent_gap':{category:'wall',title:'Защитное решение стены',scope:'Пунктир обозначает нерешённые элементы. Воздушный зазор, мембраны и пароизоляция выполняют разные задачи; их нельзя подменять друг другом.'},
 '13_inner_finish':{category:'wall',title:'Внутренняя отделка',scope:'Основа стены не определяет внутреннюю отделку. Состав и пригодность для конкретного помещения ещё нужно выбрать.'}
};
const validParts=new Set([...Object.keys(roleInfo),'05_roof','09_wall_core','12_cladding']);
export function materialContext({loaded=false,suspended=false,mode='assembled',layer=null,stage=0,choices={}}={}){
 const visible=loaded&&!suspended&&visibleModes.has(mode);
 let part=['wall','wall-section'].includes(mode)?'09_wall_core':mode==='facade'?'12_cladding':'05_roof';
 if(mode==='exploded')part=(validParts.has(layer)?layer:null)||assemblySteps[Math.max(0,Math.min(6,Math.trunc(stage)||0))]?.layer||'05_roof';else if(mode==='wall'&&validParts.has(layer))part=layer;
 const role=Object.hasOwn(roleInfo,part)?roleInfo[part]:null,category=role?.category||(part==='09_wall_core'?'wall':part==='12_cladding'?'facade':'roof');
 const chosen=materials.find(m=>m.category===category&&m.id===choices[category])||null;
 const item=role?null:chosen||(category==='roof'?materials.find(m=>m.id==='standing-seam'):null);
 const state=role?'unresolved':chosen?'chosen':item?'sample':'unselected';
 const title=role?.title||item?.title||(category==='wall'?'Материал стены пока не выбран':'Фасадная отделка пока не выбрана');
 const scope=role?.scope||(category==='wall'?'Выбранная основа показывается в одном учебном участке. Остальные стены дома ещё не перестраиваются.':category==='roof'?'На скатах показан внешний вид покрытия. Основание, утепление, вентиляция, крепления и применимость к уклону согласуются отдельно.':chosen?'Отделка меняет наружные плоскости и фронтоны. Проёмы и исходные деревянные акценты сохраняются; полная фасадная система ещё не утверждена.':'Сохранён исходный облик эскиза: светлые плоскости с деревянными акцентами. Он не означает выбор одной из фасадных систем.');
 const status=state==='chosen'?'Выбрано для обсуждения':state==='sample'?'Образец на модели · ещё не выбран':state==='unresolved'?'Решение по этому слою ещё не выбрано':'Решение пока открыто';
 return {visible,category,part,state,title,status,scope,materialId:item?.id||null,choiceId:chosen?.id||null,related:role&&chosen?(category==='roof'?'Покрытие в пожеланиях: ':'Основа стены в пожеланиях: ')+chosen.title+'. Это не выбор показанного слоя.':null,
  facts:item?[{label:'Что удобно',text:item.benefit},{label:'Что учесть',text:item.limitation},{label:'Теплозащита',text:item.heat}]:[],budget:item?.budget||null,
  questions:item?[...item.questions]:role?['Какой полный состав и узлы предлагаются для этого элемента?','Как решение согласуется с остальными слоями и условиями участка?']:[],
  reviewStatus:'draft',price:null,technicalValues:null,geometryChanged:false};
}
