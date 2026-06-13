import React from 'react';
import { X } from 'lucide-react';
import { resolveEstimatePackage } from '../utils/estimatePackage';

export default function GenerateEstimateModal({
  showGenerateEstimate,
  setShowGenerateEstimate,
  generating,
  setGenerating,
  C,
  card,
  inp,
  btnO,
  btnG,
  generateForm,
  setGenerateForm,
  projects,
  pricelists,
  estimatePackages,
  nextEstimateVersionFor,
  API,
  enrichEstimateMeasurementBasis,
  estimatesList,
  setEstimatesList,
  setSelectedEstimate,
  activeEstimateFromList,
  isGlobalEstimateTemplate,
  sameEstimateGroup,
  queueEstimateDiffReviewTask,
  autoReconcileEstimateChanges,
  queueEstimateQualityReviewTask,
  queueEstimateNormReviewTask,
}) {
  if (!showGenerateEstimate) return null;

  const generate = async () => {
    if(!generateForm.description.trim()) return;
    setGenerating(true);
    try{
      const genVersion=generateForm.version||nextEstimateVersionFor(generateForm);
      const res=await fetch(API+'/ai-generate-estimate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...generateForm,version:genVersion})});
      const data=await res.json();
      if(!res.ok||!data.ok){alert('ИИ не справился: '+(data.detail||'попробуйте ещё раз с более детальным описанием'));setGenerating(false);return;}
      const est={id:data.id,name:data.name,projectId:data.projectId||'',projectName:data.projectName||'',version:data.version||genVersion,smetaType:data.smetaType||generateForm.smetaType||'Заказчик',workPackage:data.workPackage||generateForm.workPackage||'Основная',status:data.status||generateForm.status||'Активная',sections:enrichEstimateMeasurementBasis(data.sections||[])};
      const diffBase=activeEstimateFromList((estimatesList||[]).filter(e=>est.status==='Активная'&&!isGlobalEstimateTemplate(e)&&sameEstimateGroup(e,est)&&e.status==='Активная'));
      const nextEstimates=[...(estimatesList||[]).map(e=>(est.status==='Активная'&&!isGlobalEstimateTemplate(e)&&sameEstimateGroup(e,est))?{...e,status:'Архив'}:e),est];
      setEstimatesList(nextEstimates);
      setSelectedEstimate(est);
      if(diffBase) {
        await queueEstimateDiffReviewTask(diffBase,est,'ИИ-смета создана');
        await autoReconcileEstimateChanges(diffBase,est,'ИИ-смета создана');
      }
      await queueEstimateQualityReviewTask(est, 'ИИ-смета создана');
      await queueEstimateNormReviewTask(est, 'ИИ-смета создана', nextEstimates);
      setShowGenerateEstimate(false);
      setGenerating(false);
      alert('Смета создана! Проверьте позиции и объёмы — можно редактировать вручную.');
    }catch(e){alert('Ошибка: '+e.message);setGenerating(false);}
  };

  return (
    <div onClick={()=>!generating&&setShowGenerateEstimate(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:650,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'22px',width:'520px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'4px'}}>
          <span style={{fontSize:'22px'}}>🤖</span>
          <b style={{color:C.text,fontSize:'15px'}}>Сгенерировать смету через ИИ</b>
        </div>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 14px'}}>ИИ соберёт черновик из позиций прайс-листа на основе вашего описания. Объёмы и цены потом можно поправить вручную.</p>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'10px'}}>
          <select value={generateForm.projectId} onChange={e=>{const p=projects.find(pr=>pr.id===Number(e.target.value));const next={...generateForm,projectId:e.target.value,projectName:p?p.name:'',pricelistId:p&&p.pricelistId?String(p.pricelistId):generateForm.pricelistId,name:p?'Смета — '+p.name:generateForm.name};setGenerateForm({...next,version:nextEstimateVersionFor(next)});}} style={{...inp,marginBottom:0}}>
            <option value=''>Без привязки к проекту</option>
            {projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select value={generateForm.pricelistId} onChange={e=>setGenerateForm({...generateForm,pricelistId:e.target.value})} style={{...inp,marginBottom:0}}>
            <option value=''>Без прайс-листа</option>
            {pricelists.map(pl=><option key={pl.id} value={pl.id}>📋 {pl.name}</option>)}
          </select>
          <input
            placeholder='Название сметы'
            value={generateForm.name}
            onChange={e=>{
              const next = {
                ...generateForm,
                name: e.target.value,
                workPackage: resolveEstimatePackage(generateForm.workPackage, e.target.value, generateForm.description),
              };
              setGenerateForm({...next,version:nextEstimateVersionFor(next)});
            }}
            style={{...inp,marginBottom:0}}
          />
          <input placeholder='Версия' value={generateForm.version||nextEstimateVersionFor(generateForm)} onChange={e=>setGenerateForm({...generateForm,version:e.target.value})} style={{...inp,marginBottom:0}}/>
          <input placeholder='Площадь (м²)' type='number' step='any' inputMode='decimal' value={generateForm.area} onChange={e=>setGenerateForm({...generateForm,area:e.target.value})} style={{...inp,marginBottom:0}}/>
          <select value={generateForm.smetaType||'Заказчик'} onChange={e=>{const next={...generateForm,smetaType:e.target.value};setGenerateForm({...next,version:nextEstimateVersionFor(next)});}} style={{...inp,marginBottom:0}}>
            <option value="Заказчик">📋 Смета заказчика</option>
            <option value="Работы">👷 Смета работ</option>
            <option value="Материалы">📦 Смета материалов</option>
          </select>
          <select value={generateForm.workPackage||'Основная'} onChange={e=>{const next={...generateForm,workPackage:e.target.value};setGenerateForm({...next,version:nextEstimateVersionFor(next)});}} style={{...inp,marginBottom:0}}>
            {estimatePackages.map(pkg=><option key={pkg} value={pkg}>📁 {pkg}</option>)}
          </select>
        </div>
        <textarea placeholder='Опишите объект как можно подробнее: тип помещения, что нужно сделать, материалы, особенности. Например: "Квартира 3-комн 75 м² в новостройке без отделки. Стяжка, штукатурка/шпатлёвка/окраска стен, плитка в санузле и кухне, ламинат в комнатах, натяжные потолки. Установка межкомнатных дверей (4 шт), сантехника под ключ."' rows={6} value={generateForm.description} onChange={e=>setGenerateForm({...generateForm,description:e.target.value})} style={{...inp,marginBottom:'10px',resize:'vertical',fontFamily:'inherit',fontSize:'13px',lineHeight:'1.5'}}/>
        <div style={{display:'flex',gap:'8px',justifyContent:'flex-end',marginTop:'8px'}}>
          <button onClick={()=>setShowGenerateEstimate(false)} disabled={generating} style={btnG}><X size={14}/>Отмена</button>
          <button disabled={generating||!generateForm.description.trim()} onClick={generate} style={{...btnO,backgroundColor:'#10b981'}}>{generating?'⏳ ИИ думает... (15-40 сек)':'✨ Сгенерировать'}</button>
        </div>
        {generating&&<p style={{color:C.textMuted,fontSize:'11px',marginTop:'10px',textAlign:'center'}}>Не закрывайте окно. ИИ собирает разделы и позиции.</p>}
      </div>
    </div>
  );
}
