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
  inp,
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
  const [editedQtyById, setEditedQtyById] = React.useState({});

  const parseQty = (value) => {
    const text = String(value ?? '').trim().replace(',', '.');
    if (!text) return 0;
    const qty = Number(text);
    return Number.isFinite(qty) ? qty : 0;
  };

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
          const confidence = Number(s.confidence||0) > 1 ? Number(s.confidence||0) / 100 : Number(s.confidence||0);
          const hasEditedQty = Object.prototype.hasOwnProperty.call(editedQtyById, s.id);
          const qtyInputValue = hasEditedQty ? editedQtyById[s.id] : (s.suggestedQtyPerUnit ? String(s.suggestedQtyPerUnit).replace('.', ',') : '');
          const qtyPerUnit = parseQty(qtyInputValue);
          const hasValidQty = qtyPerUnit > 0;
          const canAcceptGlobal = hasValidQty && confidence >= 0.7;
          const confidenceLabel = confidence >= 0.7 ? 'высокая' : confidence >= 0.5 ? 'средняя' : 'слабая';
          const confidenceColor = confidence >= 0.7 ? C.success : confidence >= 0.5 ? C.warning : C.danger;
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
          const originalQty = Number(s.suggestedQtyPerUnit || 0);
          const qtyChanged = hasValidQty && originalQty > 0 && Math.abs(qtyPerUnit - originalQty) > 0.000001;
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
                <label style={{color:C.textMuted,fontSize:'10px',textTransform:'uppercase',display:'block',marginBottom:'4px'}}>Норма расхода</label>
                <div style={{display:'grid',gridTemplateColumns:'minmax(86px,1fr) auto',gap:'6px',alignItems:'center'}}>
                  <input
                    value={qtyInputValue}
                    onChange={e=>setEditedQtyById(prev=>({...prev,[s.id]:e.target.value}))}
                    inputMode="decimal"
                    placeholder="0"
                    disabled={isPreview}
                    style={{...inp,marginBottom:0,padding:'7px 8px',fontSize:'12px',minHeight:'32px',borderColor:hasValidQty?C.border:C.dangerBorder}}
                  />
                  <span style={{color:C.textSec,fontSize:'12px',fontWeight:'700',whiteSpace:'nowrap'}}>{s.materialUnit||''} / {s.workUnit||'ед.'}</span>
                </div>
                {qtyChanged&&<p style={{color:C.warning,margin:'3px 0 0',fontSize:'10px'}}>AI: {originalQty.toLocaleString('ru-RU')} {s.materialUnit||''}</p>}
                {!hasValidQty&&!isPreview&&<p style={{color:C.danger,margin:'3px 0 0',fontSize:'10px'}}>Расход должен быть больше 0</p>}
                <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'11px'}}>Уверенность: <b style={{color:confidenceColor}}>{confidenceLabel} {Math.round(confidence*100)}%</b> · {sourceLabel} · примеров: {s.sampleCount||0}</p>
              </div>
              <div style={{display:'flex',gap:'6px',justifyContent:isMobile?'flex-start':'flex-end',flexWrap:'wrap'}}>
                {isPreview ? <>
                  <span style={badge(C.textMuted,C.bgGray,C.border)}>Без сохранения</span>
                </> : <>
                  <button onClick={()=>acceptMaterialNormSuggestion(s.id,{qtyPerUnit})} disabled={!canAcceptGlobal} title={!hasValidQty?'Укажите расход больше 0':canAcceptGlobal?'Записать в глобальный справочник компании':'Слабую норму нельзя писать глобально: примите в объект или создайте поручение'} style={btnState(btnGr,!canAcceptGlobal,{padding:'6px 9px',fontSize:'11px'})}><Check size={12}/>В справочник</button>
                  <button onClick={()=>acceptMaterialNormSuggestionAsOverride(s.id,{qtyPerUnit})} disabled={!hasValidQty} style={btnState(btnB,!hasValidQty,{padding:'6px 9px',fontSize:'11px'})}><Check size={12}/>В объект</button>
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
