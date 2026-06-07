import React from 'react';
import { Check } from 'lucide-react';

export default function ToolReturnModal({
  showReturnToolModal,
  setShowReturnToolModal,
  C,
  card,
  inp,
  btnG,
  btnGr,
  returnToolCondition,
  setReturnToolCondition,
  returnTool,
}) {
  if (!showReturnToolModal) return null;
  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}}>
      <div style={{...card,padding:'30px',width:'400px'}}>
        <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{'Вернуть: '+showReturnToolModal.name}</h3>
        <p style={{color:C.textSec,fontSize:'13px',marginBottom:'15px'}}>{'От: '+showReturnToolModal.masterName}</p>
        <select value={returnToolCondition} onChange={e=>setReturnToolCondition(e.target.value)} style={inp}><option value="Исправен">Исправен</option><option value="Требует ремонта">Требует ремонта</option><option value="Сломан">Сломан</option><option value="Утерян">Утерян</option></select>
        <div style={{display:'flex',gap:'10px'}}><button onClick={()=>returnTool(showReturnToolModal)} style={btnGr}><Check size={14}/>Вернуть</button><button onClick={()=>setShowReturnToolModal(null)} style={btnG}>Отмена</button></div>
      </div>
    </div>
  );
}
