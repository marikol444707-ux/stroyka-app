import React from 'react';
import { X } from 'lucide-react';

export default function PricelistFromEstimateModal({
  showFromEstimate,
  setShowFromEstimate,
  creatingFromEstimate,
  setCreatingFromEstimate,
  C,
  card,
  inp,
  btnO,
  btnG,
  fromEstimateForm,
  setFromEstimateForm,
  estimatesList,
  API,
  loadAll,
  setSelectedPricelist,
  loadPricelistItems,
}) {
  if (!showFromEstimate) return null;

  const createPricelist = async () => {
    setCreatingFromEstimate(true);
    try{
      const res=await fetch(API+'/pricelists/from-estimate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(fromEstimateForm)});
      const data=await res.json();
      if(!res.ok||!data.ok){alert('Не удалось создать: '+(data.detail||'ошибка'));setCreatingFromEstimate(false);return;}
      await loadAll();
      const newPl=await fetch(API+'/pricelists').then(r=>r.json()).then(arr=>(Array.isArray(arr)?arr.find(p=>p.id===data.id):null));
      if(newPl){setSelectedPricelist(newPl);await loadPricelistItems(newPl.id);}
      setShowFromEstimate(false);
      setCreatingFromEstimate(false);
      alert('Прайс-лист «'+data.name+'» создан! Позиций: '+data.itemsCount);
    }catch(e){alert('Ошибка: '+e.message);setCreatingFromEstimate(false);}
  };

  return (
    <div onClick={()=>!creatingFromEstimate&&setShowFromEstimate(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:650,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'22px',width:'480px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'4px'}}>
          <span style={{fontSize:'22px'}}>📋</span>
          <b style={{color:C.text,fontSize:'15px'}}>Создать прайс-лист из сметы</b>
        </div>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 14px'}}>Все позиции выбранной сметы попадут в прайс. Категория = название раздела сметы. Цены подтянутся из сметы — потом можно поправить вручную.</p>
        <select value={fromEstimateForm.estimateId} onChange={e=>{const est=estimatesList.find(es=>String(es.id)===e.target.value);setFromEstimateForm({...fromEstimateForm,estimateId:e.target.value,name:est?'Прайс из «'+est.name+'»':fromEstimateForm.name});}} style={inp}>
          <option value=''>Выберите смету *</option>
          {estimatesList.map(e=><option key={e.id} value={e.id}>{e.name}{e.projectName?' — '+e.projectName:''}</option>)}
        </select>
        <input placeholder='Название прайс-листа' value={fromEstimateForm.name} onChange={e=>setFromEstimateForm({...fromEstimateForm,name:e.target.value})} style={inp}/>
        <select value={fromEstimateForm.forWho} onChange={e=>setFromEstimateForm({...fromEstimateForm,forWho:e.target.value})} style={inp}>
          <option value=''>Для кого (необязательно)</option>
          {['Общий','Электрики','Сантехники','Каменщики','Отделочники','Кровельщики','Монтажники'].map(r=><option key={r}>{r}</option>)}
        </select>
        <label style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'4px'}}>{'Коэффициент: ×'+fromEstimateForm.coefficient}</label>
        <input type='range' min='0.5' max='3' step='0.1' value={fromEstimateForm.coefficient} onChange={e=>setFromEstimateForm({...fromEstimateForm,coefficient:Number(e.target.value)})} style={{width:'100%',marginBottom:'10px',accentColor:C.accent}}/>
        <div style={{display:'flex',gap:'8px',justifyContent:'flex-end',marginTop:'8px'}}>
          <button onClick={()=>setShowFromEstimate(false)} disabled={creatingFromEstimate} style={btnG}><X size={14}/>Отмена</button>
          <button disabled={creatingFromEstimate||!fromEstimateForm.estimateId} onClick={createPricelist} style={btnO}>{creatingFromEstimate?'⏳ Создаю...':'✨ Создать'}</button>
        </div>
      </div>
    </div>
  );
}
