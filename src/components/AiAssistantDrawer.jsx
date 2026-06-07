import React from 'react';
import { X } from 'lucide-react';

export default function AiAssistantDrawer({
  showAiAssistant,
  setShowAiAssistant,
  C,
  inp,
  btnG,
  btnO,
  aiChat,
  aiLoading,
  aiMessage,
  setAiMessage,
  sendAiMessage,
  chatEndRef,
}) {
  if (!showAiAssistant) return null;
  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'flex-end',zIndex:1500}}>
      <div style={{width:'420px',backgroundColor:C.bgWhite,display:'flex',flexDirection:'column',boxShadow:'-4px 0 30px rgba(0,0,0,0.15)'}}>
        <div style={{padding:'16px 20px',borderBottom:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',backgroundColor:C.sidebar}}>
          <div><b style={{color:'white',fontSize:'15px'}}>🤖 ИИ Помощник</b><p style={{color:'rgba(255,255,255,0.5)',margin:'2px 0',fontSize:'12px'}}>Знает нормы СНиП, расценки, материалы</p></div>
          <button onClick={()=>setShowAiAssistant(false)} style={{backgroundColor:'transparent',border:'none',cursor:'pointer',color:'white'}}><X size={20}/></button>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'16px',display:'flex',flexDirection:'column',gap:'12px'}}>
          {aiChat.length===0&&(<div style={{textAlign:'center',padding:'30px',color:C.textMuted}}><div style={{fontSize:'40px',marginBottom:'10px'}}>🏗️</div><b style={{color:C.text}}>Спросите меня!</b><div style={{display:'flex',flexDirection:'column',gap:'8px',marginTop:'16px'}}>{['Сколько цемента нужно для стяжки 50м2?','Нормы расхода штукатурки на 1м2?','Как рассчитать количество кирпича?','Какие СНиП для жилых домов?'].map(q=>(<button key={q} onClick={()=>setAiMessage(q)} style={{...btnG,fontSize:'12px',textAlign:'left',justifyContent:'flex-start'}}>{q}</button>))}</div></div>)}
          {aiChat.map((msg,i)=>(<div key={i} style={{display:'flex',justifyContent:msg.role==='user'?'flex-end':'flex-start'}}><div style={{maxWidth:'85%',backgroundColor:msg.role==='user'?C.accent:C.bg,color:msg.role==='user'?'white':C.text,padding:'10px 14px',borderRadius:msg.role==='user'?'16px 16px 4px 16px':'16px 16px 16px 4px',border:'1.5px solid '+(msg.role==='user'?C.accent:C.border),fontSize:'13px',lineHeight:'1.5'}}>{msg.content}<div style={{fontSize:'10px',color:msg.role==='user'?'rgba(255,255,255,0.6)':C.textMuted,marginTop:'4px',textAlign:'right'}}>{msg.time}</div></div></div>))}
          {aiLoading&&<div style={{display:'flex',justifyContent:'flex-start'}}><div style={{backgroundColor:C.bg,padding:'10px 14px',borderRadius:'16px',border:'1.5px solid '+C.border,color:C.textSec,fontSize:'13px'}}>Думаю...</div></div>}
          <div ref={chatEndRef}/>
        </div>
        <div style={{padding:'12px',borderTop:'1.5px solid '+C.border}}>
          <div style={{display:'flex',gap:'8px'}}><input placeholder="Задайте вопрос..." value={aiMessage} onChange={e=>setAiMessage(e.target.value)} onKeyDown={e=>e.key==='Enter'&&!aiLoading&&sendAiMessage()} style={{...inp,marginBottom:0,flex:1,fontSize:'13px'}} disabled={aiLoading}/><button onClick={sendAiMessage} disabled={aiLoading} style={btnO}>➤</button></div>
        </div>
      </div>
    </div>
  );
}
