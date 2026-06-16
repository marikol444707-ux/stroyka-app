import React from 'react';

export default function MaterialNormCoverageSummaryBadges({
  C,
  badge,
  okCount,
  skippedCount,
  missingCount,
  unlinkedCount,
  shortageCount = 0,
  invalidQtyCount,
  zeroQtyCount,
  infoCount,
  totalRows,
}) {
  return (
    <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginBottom:'10px'}}>
      <span style={badge(C.success,C.successLight,C.successBorder)}>{'Покрыто: '+okCount}</span>
      <span style={badge(C.textSec,C.bgGray,C.border)}>{'Без материалов: '+skippedCount}</span>
      <span style={badge(C.warning,C.warningLight,C.warningBorder)}>{'Нет нормы: '+missingCount}</span>
      <span style={badge(C.warning,C.warningLight,C.warningBorder)}>{'Нехватка: '+shortageCount}</span>
      <span style={badge(C.warning,C.warningLight,C.warningBorder)}>{'Материал без работы: '+unlinkedCount}</span>
      <span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>{'Некорректно: '+invalidQtyCount}</span>
      <span style={badge(C.warning,C.warningLight,C.warningBorder)}>{'Без количества: '+zeroQtyCount}</span>
      <span style={badge(C.info,C.infoLight,C.infoBorder)}>{'Нет материала в разделе: '+infoCount}</span>
      <span style={badge(C.textSec,C.bgGray,C.border)}>{'Всего строк: '+totalRows}</span>
    </div>
  );
}
