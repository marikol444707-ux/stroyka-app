import React from 'react';
import { Plus } from 'lucide-react';

export default function EstimateDistributeBrigadesPanel({
  C,
  card,
  inp,
  btnO,
  distributeBrigades,
  setDistributeBrigades,
  newDistributeBrigade,
  setNewDistributeBrigade,
  pricelists,
}) {
  return (
    <div style={{...card,padding:'10px',marginBottom:'10px',backgroundColor:C.bg}}>
      <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'6px'}}>Бригады, которым раздаём:</b>
      <div style={{display:'flex',flexWrap:'wrap',gap:'6px',marginBottom:'8px'}}>
        {distributeBrigades.map((b,i)=>(
          <span key={i} style={{padding:'4px 10px',borderRadius:'12px',backgroundColor:C.accentLight,color:C.accent,fontSize:'11px',display:'flex',alignItems:'center',gap:'6px'}}>
            {b.name}
            <button onClick={()=>setDistributeBrigades(prev=>prev.filter((_,idx)=>idx!==i))} style={{background:'none',border:'none',cursor:'pointer',color:C.danger}}>×</button>
          </span>
        ))}
        {distributeBrigades.length===0&&<span style={{fontSize:'11px',color:C.textMuted}}>Пока пусто — добавь бригады ниже</span>}
      </div>
      <div style={{display:'flex',gap:'4px'}}>
        <input placeholder='Название бригады' value={newDistributeBrigade.brigadeName} onChange={e=>setNewDistributeBrigade({...newDistributeBrigade,brigadeName:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px',flex:1}}/>
        <select value={newDistributeBrigade.pricelistId} onChange={e=>setNewDistributeBrigade({...newDistributeBrigade,pricelistId:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px',width:'160px'}}><option value=''>Прайс (необязат.)</option>{pricelists.map(pl=><option key={pl.id} value={pl.id}>{pl.name}</option>)}</select>
        <button onClick={()=>{
          if(!newDistributeBrigade.brigadeName.trim()) return;
          setDistributeBrigades(prev=>[...prev,{name:newDistributeBrigade.brigadeName.trim(),contractorType:newDistributeBrigade.contractorType,pricelistId:newDistributeBrigade.pricelistId}]);
          setNewDistributeBrigade({brigadeName:'',contractorType:'Своя бригада',pricelistId:''});
        }} style={{...btnO,fontSize:'12px',padding:'6px 10px'}}><Plus size={12}/>Добавить</button>
      </div>
    </div>
  );
}
