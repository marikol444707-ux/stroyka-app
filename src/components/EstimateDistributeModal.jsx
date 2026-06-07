import React from 'react';
import { Bot, X } from 'lucide-react';
import EstimateDistributeBrigadesPanel from './EstimateDistributeBrigadesPanel';
import EstimateDistributeItemsTable from './EstimateDistributeItemsTable';

export default function EstimateDistributeModal({
  showDistribute,
  setShowDistribute,
  selectedEstimate,
  distributing,
  setDistributing,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  distributeBrigades,
  setDistributeBrigades,
  newDistributeBrigade,
  setNewDistributeBrigade,
  pricelists,
  distributeAssignments,
  setDistributeAssignments,
  API,
  loadAll,
}) {
  if (!showDistribute || !selectedEstimate) return null;

  const suggestWithAi = async () => {
    if(distributeBrigades.length===0){alert('Сначала добавьте бригады');return;}
    setDistributing(true);
    try{
      const res=await fetch(API+'/estimates/'+selectedEstimate.id+'/ai-distribute-suggest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({brigadeNames:distributeBrigades.map(b=>b.name)})});
      const data=await res.json();
      if(data.ok&&Array.isArray(data.assignments)){
        const newAssign={};
        let flatIdx=0;
        (selectedEstimate.sections||[]).forEach((s,si)=>(s.items||[]).forEach((it,ii)=>{
          const a=data.assignments.find(a=>a.itemIndex===flatIdx);
          if(a) newAssign[si+'-'+ii]=a.brigadeName;
          flatIdx++;
        }));
        setDistributeAssignments(newAssign);
        alert('ИИ распределил позиции — проверьте и поправьте если нужно');
      }else alert('ИИ не справился, распределите вручную');
    }catch(e){alert('Ошибка ИИ: '+e.message);}
    setDistributing(false);
  };

  const createContracts = async () => {
    const assignments=[];
    (selectedEstimate.sections||[]).forEach((s,si)=>(s.items||[]).forEach((it,ii)=>{
      const bname=distributeAssignments[si+'-'+ii];
      if(bname){
        const bdata=distributeBrigades.find(b=>b.name===bname);
        assignments.push({section:s.name,name:it.name,unit:it.unit||'шт',quantity:Number(it.quantity||0),priceSmeta:Number(it.priceWork||0),brigadeName:bname,contractorType:bdata?.contractorType||'Своя бригада',pricelistId:bdata?.pricelistId||null});
      }
    }));
    if(!assignments.length){alert('Ничего не назначено');return;}
    setDistributing(true);
    try{
      const res=await fetch(API+'/estimates/'+selectedEstimate.id+'/distribute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({assignments,defaultCoefficient:0.6})});
      const data=await res.json();
      if(!res.ok||!data.ok){alert('Ошибка: '+(data.detail||'не удалось'));setDistributing(false);return;}
      await loadAll();
      setShowDistribute(false);
      setDistributing(false);
      alert('Создано расчётов с бригадами: '+data.createdContracts.length+'\n\n'+data.createdContracts.map(c=>'• '+c.brigadeName+' ('+c.itemsCount+' поз., '+Math.round(c.totalAmount).toLocaleString('ru-RU')+' ₽)').join('\n'));
    }catch(e){alert('Ошибка: '+e.message);setDistributing(false);}
  };

  return (
    <div onClick={()=>!distributing&&setShowDistribute(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:650,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'22px',width:'720px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'4px'}}>
          <span style={{fontSize:'22px'}}>👷</span>
          <b style={{color:C.text,fontSize:'15px'}}>Распределить смету по бригадам</b>
        </div>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 14px'}}>Каждой позиции выбери бригаду. Из этого автоматически создадутся расчёты с бригадами с пересчётом цен по коэффициенту бригадного прайса (или 0.6 по умолчанию).</p>
        <EstimateDistributeBrigadesPanel C={C} card={card} inp={inp} btnO={btnO} distributeBrigades={distributeBrigades} setDistributeBrigades={setDistributeBrigades} newDistributeBrigade={newDistributeBrigade} setNewDistributeBrigade={setNewDistributeBrigade} pricelists={pricelists}/>
        <EstimateDistributeItemsTable C={C} inp={inp} selectedEstimate={selectedEstimate} distributeAssignments={distributeAssignments} setDistributeAssignments={setDistributeAssignments} distributeBrigades={distributeBrigades}/>
        <div style={{display:'flex',gap:'8px',justifyContent:'space-between',marginTop:'12px'}}>
          <button onClick={suggestWithAi} disabled={distributing||distributeBrigades.length===0} style={{...btnB,backgroundColor:'#10b981',color:'white',borderColor:'#059669',fontSize:'12px'}}><Bot size={13}/>🤖 ИИ распределит</button>
          <div style={{display:'flex',gap:'8px'}}>
            <button onClick={()=>setShowDistribute(false)} disabled={distributing} style={btnG}><X size={14}/>Отмена</button>
            <button disabled={distributing||Object.keys(distributeAssignments).length===0} onClick={createContracts} style={btnO}>{distributing?'⏳...':'✨ Создать расчёты'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
