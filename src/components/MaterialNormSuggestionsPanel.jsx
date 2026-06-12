import React from 'react';
import { Bot, Check, FileText, ShoppingCart, X } from 'lucide-react';
import MaterialNormSuggestionsHeader from './MaterialNormSuggestionsHeader';

export default function MaterialNormSuggestionsPanel({
  C,
  badge,
  btnB,
  btnG,
  btnGr,
  btnO,
  btnR,
  btnState,
  card,
  isMobile,
  suggestions,
  materialNormSuggestionLoading,
  generateMaterialNormSuggestions,
  canEditMaterialNorms,
  createEstimateFromNormSuggestions,
  acceptMaterialNormSuggestion,
  acceptMaterialNormSuggestionAsOverride,
  createTaskFromMaterialNormSuggestion,
  rejectMaterialNormSuggestion
}) {
  if(!suggestions.length) return null;
  const canEdit = canEditMaterialNorms();

  return (
    <div style={{...card,padding:'14px',marginBottom:'16px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}>
      <MaterialNormSuggestionsHeader
        C={C}
        btnG={btnG}
        btnState={btnState}
        materialNormSuggestionLoading={materialNormSuggestionLoading}
        generateMaterialNormSuggestions={generateMaterialNormSuggestions}
      />
      {canEdit&&<div style={{display:'flex',gap:'8px',flexWrap:'wrap',margin:'0 0 10px'}}>
        <button onClick={()=>createEstimateFromNormSuggestions(false)} disabled={materialNormSuggestionLoading} style={btnState(btnO,materialNormSuggestionLoading,{padding:'7px 10px',fontSize:'12px'})}><FileText size={13}/>Черновик сметы из норм</button>
        <button onClick={()=>createEstimateFromNormSuggestions(true)} disabled={materialNormSuggestionLoading} style={btnState(btnGr,materialNormSuggestionLoading,{padding:'7px 10px',fontSize:'12px'})}><ShoppingCart size={13}/>Черновик + заявка</button>
      </div>}
      <div style={{display:'grid',gap:'8px'}}>
        {suggestions.slice(0,12).map(s=>{
          const isPreview = s.previewOnly || s.status==='Предпросмотр';
          const sevColor=s.severity==='Критично'?C.danger:s.severity==='Не хватает данных'?C.warning:C.info;
          const sourceLabel={
            'estimate-parent':'связка из сметы',
            'estimate-search':'найдено по названию',
            'rules+yandexgpt':'проверено AI',
            rules:'правило системы'
          }[s.source] || s.source || 'расчёт системы';
          const typeLabel={
            without_norm:'Списано без нормы',
            over_norm:'Перерасход нормы',
            estimate_material_without_norm:'Материал сметы без нормы'
          }[s.suggestionType] || 'Проверить норму';
          return(<div key={s.id} style={{...card,padding:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
            <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'minmax(220px,1.4fr) minmax(240px,1.4fr) 180px auto',gap:'10px',alignItems:'center'}}>
              <div style={{minWidth:0}}>
                <span style={badge(sevColor,C.bgGray,C.border)}>{typeLabel}</span>
                {isPreview&&<span style={{...badge(C.info,C.infoLight,C.infoBorder),marginLeft:'6px'}}>Предпросмотр</span>}
                <b style={{display:'block',color:C.text,fontSize:'13px',marginTop:'6px'}}>{s.materialName||'Материал'}</b>
                <p style={{color:C.textMuted,margin:'3px 0 0',fontSize:'11px'}}>{s.projectName||'—'}{s.sectionName?' · '+s.sectionName:''}</p>
              </div>
              <div style={{minWidth:0}}>
                <span style={{color:C.textMuted,fontSize:'10px',textTransform:'uppercase'}}>Работа</span>
                <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'12px'}}>{s.workName||'—'}</p>
                {(s.aiSummary||s.reason)&&<p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>{s.aiSummary||s.reason}</p>}
              </div>
              <div>
                <span style={{color:C.textMuted,fontSize:'10px',textTransform:'uppercase'}}>Предложение</span>
                <p style={{color:C.success,margin:'2px 0 0',fontSize:'13px',fontWeight:'800'}}>{s.suggestedQtyPerUnit?Number(s.suggestedQtyPerUnit).toLocaleString('ru-RU'):'—'} {s.materialUnit||''} / {s.workUnit||'ед.'}</p>
                <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'11px'}}>Уверенность: {Math.round(Number(s.confidence||0)*100)}% · {sourceLabel} · примеров: {s.sampleCount||0}</p>
              </div>
              <div style={{display:'flex',gap:'6px',justifyContent:isMobile?'flex-start':'flex-end',flexWrap:'wrap'}}>
                {isPreview ? <>
                  <span style={badge(C.textMuted,C.bgGray,C.border)}>Без сохранения</span>
                </> : <>
                  <button onClick={()=>acceptMaterialNormSuggestion(s.id)} disabled={!s.suggestedQtyPerUnit} style={btnState(btnGr,!s.suggestedQtyPerUnit,{padding:'6px 9px',fontSize:'11px'})}><Check size={12}/>Принять</button>
                  <button onClick={()=>acceptMaterialNormSuggestionAsOverride(s.id)} disabled={!s.suggestedQtyPerUnit} style={btnState(btnB,!s.suggestedQtyPerUnit,{padding:'6px 9px',fontSize:'11px'})}><Check size={12}/>В объект</button>
                  <button onClick={()=>createTaskFromMaterialNormSuggestion(s.id)} style={{...btnB,padding:'6px 9px',fontSize:'11px'}}><Bot size={12}/>Поручение</button>
                  <button onClick={()=>rejectMaterialNormSuggestion(s.id)} style={{...btnR,padding:'6px 9px',fontSize:'11px'}}><X size={12}/></button>
                </>}
              </div>
            </div>
          </div>);
        })}
        {suggestions.length>12&&<p style={{color:C.textMuted,fontSize:'11px',margin:'4px 0 0'}}>Показано 12 из {suggestions.length}. Остальные останутся в списке после обработки верхних.</p>}
      </div>
    </div>
  );
}
