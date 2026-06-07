import React from 'react';

export default function AiChatMessagesList({C, aiMessages, aiLoading}) {
  return (
    <div style={{flex:1,overflowY:'auto',padding:'12px',display:'flex',flexDirection:'column',gap:'8px',backgroundColor:C.bg}}>
      {aiMessages.map((msg,i)=>(
        <div key={i} style={{display:'flex',justifyContent:msg.role==='user'?'flex-end':'flex-start'}}>
          <div style={{maxWidth:'85%',padding:'8px 12px',borderRadius:msg.role==='user'?'16px 16px 4px 16px':'16px 16px 16px 4px',backgroundColor:msg.role==='user'?C.accent:C.bgWhite,color:msg.role==='user'?'white':C.text,fontSize:'13px',lineHeight:'1.5',boxShadow:'0 1px 3px rgba(0,0,0,0.08)',border:msg.role==='user'?'none':'1.5px solid '+C.border,whiteSpace:'pre-wrap'}}>
            {msg.content}
          </div>
        </div>
      ))}
      {aiLoading&&(<div style={{display:'flex',justifyContent:'flex-start'}}><div style={{padding:'8px 12px',borderRadius:'16px 16px 16px 4px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,fontSize:'13px',color:C.textSec}}>⏳ Думаю...</div></div>)}
    </div>
  );
}
