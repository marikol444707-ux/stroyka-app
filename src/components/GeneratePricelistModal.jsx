import React from 'react';
import { X } from 'lucide-react';

export default function GeneratePricelistModal({
  showGeneratePricelist,
  setShowGeneratePricelist,
  generatingPricelist,
  setGeneratingPricelist,
  C,
  card,
  inp,
  btnO,
  btnG,
  generatePricelistForm,
  setGeneratePricelistForm,
  API,
  loadAll,
  setSelectedPricelist,
  loadPricelistItems,
}) {
  if (!showGeneratePricelist) return null;

  const generate = async () => {
    if(!generatePricelistForm.description.trim()) return;
    setGeneratingPricelist(true);
    try{
      const res=await fetch(API+'/ai-generate-pricelist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(generatePricelistForm)});
      const data=await res.json();
      if(!res.ok||!data.ok){alert('ИИ не справился: '+(data.detail||'попробуйте ещё раз с более детальным описанием'));setGeneratingPricelist(false);return;}
      await loadAll();
      const newPl=await fetch(API+'/pricelists').then(r=>r.json()).then(arr=>(Array.isArray(arr)?arr.find(p=>p.id===data.id):null));
      if(newPl){setSelectedPricelist(newPl);await loadPricelistItems(newPl.id);}
      setShowGeneratePricelist(false);
      setGeneratingPricelist(false);
      alert('Прайс-лист «'+data.name+'» создан! Позиций: '+data.itemsCount+'. Проверьте цены — можно редактировать вручную.');
    }catch(e){alert('Ошибка: '+e.message);setGeneratingPricelist(false);}
  };

  return (
    <div onClick={()=>!generatingPricelist&&setShowGeneratePricelist(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:650,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'22px',width:'520px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'4px'}}>
          <span style={{fontSize:'22px'}}>🤖</span>
          <b style={{color:C.text,fontSize:'15px'}}>Сгенерировать прайс-лист через ИИ</b>
        </div>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 14px'}}>Опишите для каких работ нужен прайс. ИИ соберёт список позиций с рыночными ценами по РФ 2026.</p>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'10px'}}>
          <input placeholder='Название прайс-листа' value={generatePricelistForm.name} onChange={e=>setGeneratePricelistForm({...generatePricelistForm,name:e.target.value})} style={{...inp,marginBottom:0}}/>
          <select value={generatePricelistForm.forWho} onChange={e=>setGeneratePricelistForm({...generatePricelistForm,forWho:e.target.value})} style={{...inp,marginBottom:0}}>
            <option value=''>Для кого (необязательно)</option>
            {['Электрики','Сантехники','Каменщики','Отделочники','Кровельщики','Монтажники','Общий'].map(r=><option key={r}>{r}</option>)}
          </select>
        </div>
        <textarea placeholder='Опишите подробнее: какие работы должны быть в прайсе, на какой тип объектов, какие материалы. Например: "Прайс для полного отделочного ремонта квартир и офисов: штукатурка, шпатлёвка, окраска, обои, плитка, ламинат, потолки. Включи демонтажные и подготовительные работы."' rows={6} value={generatePricelistForm.description} onChange={e=>setGeneratePricelistForm({...generatePricelistForm,description:e.target.value})} style={{...inp,marginBottom:'10px',resize:'vertical',fontFamily:'inherit',fontSize:'13px',lineHeight:'1.5'}}/>
        <label style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'4px'}}>{'Коэффициент: ×'+generatePricelistForm.coefficient}</label>
        <input type='range' min='0.5' max='3' step='0.1' value={generatePricelistForm.coefficient} onChange={e=>setGeneratePricelistForm({...generatePricelistForm,coefficient:Number(e.target.value)})} style={{width:'100%',marginBottom:'10px',accentColor:C.accent}}/>
        <div style={{display:'flex',gap:'8px',justifyContent:'flex-end',marginTop:'8px'}}>
          <button onClick={()=>setShowGeneratePricelist(false)} disabled={generatingPricelist} style={btnG}><X size={14}/>Отмена</button>
          <button disabled={generatingPricelist||!generatePricelistForm.description.trim()} onClick={generate} style={{...btnO,backgroundColor:'#10b981'}}>{generatingPricelist?'⏳ ИИ думает... (15-40 сек)':'✨ Сгенерировать'}</button>
        </div>
        {generatingPricelist&&<p style={{color:C.textMuted,fontSize:'11px',marginTop:'10px',textAlign:'center'}}>Не закрывайте окно. ИИ собирает позиции прайс-листа.</p>}
      </div>
    </div>
  );
}
