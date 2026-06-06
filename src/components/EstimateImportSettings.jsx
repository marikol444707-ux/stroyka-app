import React from 'react';

export default function EstimateImportSettings({
  inp,
  projects,
  newEstimate,
  setNewEstimate,
  nextEstimateVersionFor,
  estimatePackages,
}) {
  return (
    <>
      <select
        value={newEstimate.projectId}
        onChange={e=>{
          const p=projects.find(pr=>pr.id===Number(e.target.value));
          const next={...newEstimate,projectId:e.target.value,projectName:p?p.name:'',name:p?'Смета — '+p.name:''};
          setNewEstimate({...next,version:nextEstimateVersionFor(next)});
        }}
        style={{...inp,maxWidth:'400px'}}
      >
        <option value="">Привязать к проекту (необязательно)</option>
        {projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <select
        value={newEstimate.smetaType}
        onChange={e=>{
          const next={...newEstimate,smetaType:e.target.value};
          setNewEstimate({...next,version:nextEstimateVersionFor(next)});
        }}
        style={{...inp,maxWidth:'400px'}}
      >
        <option value="Заказчик">📋 Смета заказчика (полная ЛСР)</option>
        <option value="Работы">👷 Смета работ (для бригады)</option>
        <option value="Материалы">📦 Смета материалов (для закупки)</option>
      </select>
      <select
        value={newEstimate.workPackage||'Основная'}
        onChange={e=>{
          const next={...newEstimate,workPackage:e.target.value};
          setNewEstimate({...next,version:nextEstimateVersionFor(next)});
        }}
        style={{...inp,maxWidth:'400px'}}
      >
        {estimatePackages.map(pkg=><option key={pkg} value={pkg}>📁 {pkg}</option>)}
      </select>
      <select value={newEstimate.status||'Активная'} onChange={e=>setNewEstimate({...newEstimate,status:e.target.value})} style={{...inp,maxWidth:'400px'}}>
        <option value="Активная">Активная</option>
        <option value="Черновик">Черновик</option>
      </select>
    </>
  );
}
