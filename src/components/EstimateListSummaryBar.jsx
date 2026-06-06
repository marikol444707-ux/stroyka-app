import React from 'react';
import { Archive } from 'lucide-react';

export default function EstimateListSummaryBar({
  C,
  card,
  badge,
  btnG,
  activeCount,
  draftCount,
  archivedCount,
  templatesCount,
  showArchivedEstimates,
  setShowArchivedEstimates,
}) {
  return (
    <div style={{...card,padding:'12px 14px',marginBottom:'12px',display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',backgroundColor:C.bg}}>
      <div style={{display:'flex',gap:'8px',flexWrap:'wrap',alignItems:'center'}}>
        <span style={badge(C.success,C.successLight,C.successBorder)}>{'Активные: '+activeCount}</span>
        <span style={badge(C.warning,C.warningLight,C.warningBorder)}>{'Черновики: '+draftCount}</span>
        <span style={badge(C.textMuted,C.bgGray,C.border)}>{'Архив: '+archivedCount}</span>
        {templatesCount>0&&<span style={badge(C.info,C.infoLight,C.infoBorder)}>{'Шаблоны: '+templatesCount}</span>}
      </div>
      <button onClick={()=>setShowArchivedEstimates(!showArchivedEstimates)} style={btnG}>
        <Archive size={14}/>{showArchivedEstimates?'Скрыть архив':'Показать архив'}
      </button>
    </div>
  );
}
