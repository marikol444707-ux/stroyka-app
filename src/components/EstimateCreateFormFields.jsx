import React from 'react';
import { resolveEstimatePackage } from '../utils/estimatePackage';

export default function EstimateCreateFormFields({
  inp,
  projects,
  newEstimate,
  setNewEstimate,
  nextEstimateVersionFor,
  estimatePackages,
  templates,
}) {
  return (
    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
      <select
        value={newEstimate.projectId}
        onChange={e=>{
          const p=projects.find(pr=>pr.id===Number(e.target.value));
          const next={...newEstimate,projectId:e.target.value,projectName:p?p.name:'',name:p?'Смета — '+p.name:''};
          setNewEstimate({...next,version:nextEstimateVersionFor(next)});
        }}
        style={{...inp,marginBottom:0}}
      >
        <option value="">Выберите проект</option>
        {projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <input
        placeholder="Название сметы *"
        value={newEstimate.name}
        onChange={e=>{
          const nextName = e.target.value;
          const next = {
            ...newEstimate,
            name: nextName,
            workPackage: resolveEstimatePackage(newEstimate.workPackage, nextName),
          };
          setNewEstimate({...next,version:nextEstimateVersionFor(next)});
        }}
        style={{...inp,marginBottom:0}}
      />
      <input placeholder="Версия" value={newEstimate.version} onChange={e=>setNewEstimate({...newEstimate,version:e.target.value})} style={{...inp,marginBottom:0}}/>
      <select
        value={newEstimate.smetaType||'Заказчик'}
        onChange={e=>{
          const next={...newEstimate,smetaType:e.target.value};
          setNewEstimate({...next,version:nextEstimateVersionFor(next)});
        }}
        style={{...inp,marginBottom:0}}
      >
        <option value="Заказчик">📋 Смета заказчика</option>
        <option value="Работы">👷 Смета работ</option>
        <option value="Материалы">📦 Смета материалов</option>
      </select>
      <select
        value={newEstimate.workPackage||'Основная'}
        onChange={e=>{
          const next={...newEstimate,workPackage:e.target.value};
          setNewEstimate({...next,version:nextEstimateVersionFor(next)});
        }}
        style={{...inp,marginBottom:0}}
      >
        {estimatePackages.map(pkg=><option key={pkg} value={pkg}>📁 {pkg}</option>)}
      </select>
      <select value={newEstimate.status||'Активная'} onChange={e=>setNewEstimate({...newEstimate,status:e.target.value})} style={{...inp,marginBottom:0}}>
        <option value="Активная">Активная</option>
        <option value="Черновик">Черновик</option>
      </select>
      {templates.length>0&&(
        <select value={newEstimate.templateId||''} onChange={e=>setNewEstimate({...newEstimate,templateId:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}>
          <option value=''>📄 Пустая смета</option>
          {templates.map(t=>(<option key={t.id} value={t.id}>⭐ Из шаблона: {t.name}</option>))}
        </select>
      )}
    </div>
  );
}
