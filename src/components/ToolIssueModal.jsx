import React from 'react';
import { Check } from 'lucide-react';

export default function ToolIssueModal({
  showIssueToolModal,
  setShowIssueToolModal,
  C,
  card,
  inp,
  btnO,
  btnG,
  issueToolData,
  setIssueToolData,
  masterProfiles,
  projects,
  issueTool,
}) {
  if (!showIssueToolModal) return null;
  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}}>
      <div style={{...card,padding:'30px',width:'400px'}}>
        <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{'Выдать: '+showIssueToolModal.name}</h3>
        <select value={issueToolData.masterName} onChange={e=>setIssueToolData({...issueToolData,masterName:e.target.value})} style={inp}><option value="">Выберите мастера</option>{masterProfiles.map(mp=><option key={mp.id} value={mp.fullName}>{mp.fullName}</option>)}</select>
        <select value={issueToolData.project} onChange={e=>setIssueToolData({...issueToolData,project:e.target.value})} style={inp}><option value="">Выберите объект</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
        <select value={issueToolData.issueType} onChange={e=>setIssueToolData({...issueToolData,issueType:e.target.value})} style={inp}><option value="Временно">Временно</option><option value="В счёт зарплаты">В счёт зарплаты</option></select>
        <div style={{display:'flex',gap:'10px'}}><button onClick={()=>issueTool(showIssueToolModal)} style={btnO}><Check size={14}/>Выдать</button><button onClick={()=>setShowIssueToolModal(null)} style={btnG}>Отмена</button></div>
      </div>
    </div>
  );
}
