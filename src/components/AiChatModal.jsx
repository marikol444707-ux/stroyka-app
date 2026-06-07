import React from 'react';
import AiChatMessagesList from './AiChatMessagesList';

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
      <AiChatMessagesList C={C} aiMessages={aiMessages} aiLoading={aiLoading}/>
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
