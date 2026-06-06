import React from 'react';
import { RefreshCw } from 'lucide-react';

export default function MaterialNormSuggestionsHeader({
  C,
  btnG,
  btnState,
  materialNormSuggestionLoading,
  generateMaterialNormSuggestions,
}) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'10px'}}>
      <div>
        <b style={{color:C.warning,fontSize:'13px',display:'block'}}>🤖 AI-подсказки к нормам</b>
        <p style={{color:C.textSec,margin:'3px 0 0',fontSize:'12px'}}>Система нашла списания без нормы, перерасходы и материалы из сметы, которые не связаны со справочником норм.</p>
      </div>
      <button onClick={generateMaterialNormSuggestions} disabled={materialNormSuggestionLoading} style={btnState(btnG,materialNormSuggestionLoading)}>
        <RefreshCw size={14}/>Обновить
      </button>
    </div>
  );
}
