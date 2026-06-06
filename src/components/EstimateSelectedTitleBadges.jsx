import React from 'react';

export default function EstimateSelectedTitleBadges({
  C,
  badge,
  selectedEstimate,
  estimatesList,
  sameEstimateGroup,
  estimateStatusView,
  estimateTypeIcon,
  estimateKind,
  estimatePackage,
}) {
  const group = (estimatesList||[]).filter(e=>sameEstimateGroup(e, selectedEstimate));
  const st = estimateStatusView(selectedEstimate, group);

  return (
    <div style={{minWidth:'220px',flex:'1 1 260px'}}>
      <b style={{color:C.text,fontSize:'15px',display:'block'}}>{selectedEstimate.name}</b>
      <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginTop:'3px'}}>
        <span style={badge(st.color,st.bg,st.border)}>{st.label}</span>
        <span style={badge(C.info,C.infoLight,C.infoBorder)}>{estimateTypeIcon(estimateKind(selectedEstimate))+' '+estimateKind(selectedEstimate)}</span>
        <span style={badge(C.accent,C.accentLight,C.accentBorder)}>{'📁 '+estimatePackage(selectedEstimate)}</span>
        {selectedEstimate.version&&<span style={badge(C.textSec,C.bgGray,C.border)}>{'v'+selectedEstimate.version}</span>}
      </div>
    </div>
  );
}
