// Viewing sequence only. Distances separate the existing model for explanation.
export const assemblySeconds=12;
export const assemblySteps=[
 {at:0,title:'Дом собран',caption:'Начните разборку или выберите интересующий этап.'},
 {at:.18,title:'Покрытие кровли',caption:'Наружное покрытие защищает дом от осадков. Его характеристики зависят от конкретного изделия и всей кровельной системы.',layer:'05_roof'},
 {at:.34,title:'Обрешётка',caption:'Опора и крепление покрытия. Шаг, сечения и крепёж подбирают под выбранную кровлю.',layer:'16_roof_battens'},
 {at:.5,title:'Подкровельный слой',caption:'Место защитного слоя под покрытием. Его тип, примыкания и вентиляцию ещё нужно согласовать.',layer:'15_roof_underlay'},
 {at:.67,title:'Стропильная система',caption:'Несущая часть кровли. Сечения, соединения и нагрузки требуют расчёта.',layer:'14_rafters'},
 {at:.83,title:'Перекрытие',caption:'Слой над помещениями показан отдельно, чтобы было видно его положение в доме. Полный состав ещё не утверждён.',layer:'04_ceiling'},
 {at:1,title:'Участок стены',caption:'Наружная отделка и учебный фрагмент стены разнесены для осмотра. Полный состав и узлы требуют согласования.',layer:'09_wall_core'}
];
const ranges=[['05_roof',5.1,0,.18],['16_roof_battens',4.4,.18,.34],['15_roof_underlay',3.8,.34,.5],['14_rafters',2.7,.5,.67],['04_ceiling',1.1,.67,.83]];
export const clamp=v=>Math.max(0,Math.min(1,Number.isFinite(v)?v:0));
export function assemblyEase(value){const t=clamp(value);return t*t*t*(t*(t*6-15)+10);}
export function assemblyStage(value){const p=clamp(value);return p<=1e-9?0:assemblySteps.findIndex((s,i)=>i>0&&p<=s.at+1e-9);}
export function sampleAssembly(value,mode='exploded'){
 const p=clamp(value),pose={};
 for(const [name,height,start,end] of ranges)pose[name]={x:0,y:mode==='exploded'?height*assemblyEase((p-start)/(end-start)):0};
 const wall=mode==='wall'?p:mode==='exploded'?assemblyEase((p-.83)/.17):0;
 for(const [name,x] of Object.entries({'09_wall_core':.2,'10_insulation':.9,'11_vent_gap':1.6,'12_cladding':2.3,'13_inner_finish':-.3}))pose[name]={x:x*wall,y:0};
 return pose;
}
export function advanceAssembly(frame,dt,{reduced=false}={}){
 const direction=frame.direction<0?-1:1,p=clamp(frame.progress),end=direction<0?0:1;
 if(reduced)return {...frame,direction,progress:end,playing:false,reason:'reduced'};
 let next=clamp(p+direction*Math.max(0,Number.isFinite(dt)?dt:0)/assemblySeconds),reason='playing',playing=true;
 // Slow frames cannot skip the next explanation in guided mode.
 if(direction>0&&frame.guided){const stop=assemblySteps.find(s=>s.at>p+1e-9);if(stop&&next>=stop.at){next=stop.at;playing=false;reason='stage';}}
 if(next===end){playing=false;reason='complete';}
 return {...frame,direction,progress:next,playing,reason};
}
const cameraKeys=[
 [22,15,28,0,3.2,0],[23,16.5,27,.3,3.6,0],[24,18,25,.6,4.1,0],[24,19.5,24,1,4.5,0],[23.5,20.2,24,1,4.7,0],[23,20.5,24,1,4.7,0],[23,20.5,24,1,4.7,0]
];
export function assemblyCameraPose(value){
 const p=clamp(value),i=assemblyStage(p);if(!i)return {position:cameraKeys[0].slice(0,3),target:cameraKeys[0].slice(3)};
 const a=assemblySteps[i-1].at,b=assemblySteps[i].at,t=assemblyEase((p-a)/(b-a)),values=cameraKeys[i-1].map((v,k)=>v+(cameraKeys[i][k]-v)*t);
 return {position:values.slice(0,3),target:values.slice(3)};
}
export function bindAssemblyCamera(progress,frame){const p=clamp(progress),base=assemblyCameraPose(p);return {progress:p,offset:frame.position.map((v,i)=>v-base.position[i]),targetOffset:frame.target.map((v,i)=>v-base.target[i])};}
export function followAssemblyCamera(progress,binding){
 const p=clamp(progress),base=assemblyCameraPose(p),distance=Math.max(binding.progress,1-binding.progress,1e-6),weight=1-assemblyEase(Math.abs(p-binding.progress)/distance);
 return {position:base.position.map((v,i)=>v+binding.offset[i]*weight),target:base.target.map((v,i)=>v+binding.targetOffset[i]*weight)};
}
