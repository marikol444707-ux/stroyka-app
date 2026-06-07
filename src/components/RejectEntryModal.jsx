import React from 'react';
import { X } from 'lucide-react';

export default function RejectEntryModal({
  rejectingEntry,
  rejectComment,
  setRejectComment,
  setRejectingEntry,
  rejectJ,
  C,
  card,
  inp,
  btnR,
  btnG,
}) {
  if (!rejectingEntry) return null;
  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}}>
      <div style={{...card,padding:'30px',width:'400px'}}>
        <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>Причина отклонения</h3>
        <textarea placeholder="Укажите причину..." value={rejectComment} onChange={e=>setRejectComment(e.target.value)} style={{...inp,height:'100px',resize:'vertical'}}/>
        <div style={{display:'flex',gap:'10px'}}>
          <button onClick={()=>rejectJ(rejectingEntry,rejectComment)} style={btnR}><X size={14}/>Отклонить</button>
          <button onClick={()=>{setRejectingEntry(null);setRejectComment('');}} style={btnG}>Отмена</button>
        </div>
      </div>
    </div>
  );
}
