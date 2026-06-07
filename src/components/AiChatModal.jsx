import React from 'react';

export default function AiChatModal({showAiChat, isMobile, C, inp, btnO, aiMessages, aiLoading, aiInput, setAiInput, setShowAiChat, onSend}) {
  if (!showAiChat) return null;

  return (
    <div style={isMobile?{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:C.bgWhite,zIndex:1000,display:'flex',flexDirection:'column',overflow:'hidden'}:{position:'fixed',bottom:'80px',right:'20px',width:'480px',height:'620px',backgroundColor:C.bgWhite,borderRadius:'16px',boxShadow:'0 8px 32px rgba(0,0,0,0.15)',border:'1.5px solid '+C.border,zIndex:1000,display:'flex',flexDirection:'column',overflow:'hidden'}}>
      <div style={{padding:'14px 16px',backgroundColor:C.accent,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <div style={{display:'flex',alignItems:'center',gap:'8px'}}>
          <span style={{fontSize:'20px'}}>🤖</span>
          <div><b style={{color:'white',fontSize:'14px',display:'block'}}>ИИ Помощник</b><p style={{color:'rgba(255,255,255,0.8)',fontSize:'11px',margin:0}}>СтройКа Assistant</p></div>
        </div>
        <button onClick={()=>setShowAiChat(false)} style={{background:'none',border:'none',color:'white',cursor:'pointer',fontSize:'18px'}}>×</button>
      </div>
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
      <div style={{padding:'10px 12px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bgWhite,display:'flex',gap:'8px'}}>
        <input value={aiInput} onChange={e=>setAiInput(e.target.value)} onKeyDown={e=>{
          if(e.key==='Enter'&&!e.shiftKey&&aiInput.trim()){
            e.preventDefault();
            onSend(aiInput,'Ошибка соединения с ИИ. Проверьте подключение.');
          }
        }} placeholder='Задайте вопрос...' style={{...inp,marginBottom:0,flex:1,fontSize:'13px'}}/>
        <button onClick={()=>onSend(aiInput,'Ошибка соединения с ИИ.')} style={{...btnO,padding:'8px 14px'}}>➤</button>
      </div>
    </div>
  );
}
