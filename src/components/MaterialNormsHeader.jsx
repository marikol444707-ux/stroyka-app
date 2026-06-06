import React from 'react';
import { Bot, Eye, X } from 'lucide-react';

export default function MaterialNormsHeader({
  C,
  badge,
  btnG,
  btnO,
  btnState,
  materialNorms,
  materialNormOverrides,
  materialNormPreviewSuggestions,
  setMaterialNormPreviewSuggestions,
  materialNormSuggestionLoading,
  canEditMaterialNorms,
  generateMaterialNormSuggestions,
  activeSuggestionCount,
  fallbackNormsCount,
}) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'14px'}}>
      <div>
        <h3 style={{color:C.text,margin:'0 0 4px',fontSize:'15px',fontWeight:'700'}}>Справочник норм расхода материалов</h3>
        <p style={{color:C.textSec,margin:0,fontSize:'12px'}}>Используется в списании материалов мастером и в блоке нормативной потребности по работам.</p>
      </div>
      <div style={{display:'flex',gap:'8px',alignItems:'center',flexWrap:'wrap',justifyContent:'flex-end'}}>
        <span style={badge(C.info,C.infoLight,C.infoBorder)}>{'Норм: '+((materialNorms||[]).length || fallbackNormsCount)}</span>
        {(materialNormOverrides||[]).length>0&&<span style={badge(C.success,C.successLight,C.successBorder)}>{'Поправок: '+materialNormOverrides.length}</span>}
        {activeSuggestionCount>0&&<span style={badge(C.warning,C.warningLight,C.warningBorder)}>{'AI-предложений: '+activeSuggestionCount}</span>}
        {(materialNormPreviewSuggestions||[]).length>0&&(
          <button onClick={()=>setMaterialNormPreviewSuggestions([])} style={{...btnG,padding:'6px 10px',fontSize:'12px'}}>
            <X size={13}/>Очистить предпросмотр
          </button>
        )}
        {canEditMaterialNorms()&&(
          <button disabled={materialNormSuggestionLoading} onClick={()=>generateMaterialNormSuggestions({dryRun:true})} style={btnState(btnG,materialNormSuggestionLoading)}>
            <Eye size={14}/>Предпросмотр
          </button>
        )}
        {canEditMaterialNorms()&&(
          <button disabled={materialNormSuggestionLoading} onClick={generateMaterialNormSuggestions} style={btnState(btnO,materialNormSuggestionLoading,{border:'1.5px solid #fb923c',boxShadow:'none'})}>
            <Bot size={14}/>{materialNormSuggestionLoading?'Проверяю...':'Сохранить AI-проверку'}
          </button>
        )}
      </div>
    </div>
  );
}
