import React, { useLayoutEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { AI_MAX_MESSAGE_CHARS } from '../features/ai-assistant/aiConversation';
import './AiAssistantDrawer.css';

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
  const overlayRef = useRef(null);
  useLayoutEffect(() => {
    if (!showAiAssistant) return undefined;
    const viewport = window.visualViewport;
    const overlay = overlayRef.current;
    if (!viewport || !overlay) return undefined;
    // Safari's keyboard shrinks the visual viewport, not always 100dvh.
    // Leave pinch zoom alone so users can still zoom the conversation.
    const syncViewport = () => {
      if (viewport.scale && viewport.scale !== 1) return;
      overlay.style.height = `${viewport.height}px`;
      overlay.style.top = `${Math.max(0, viewport.offsetTop)}px`;
    };
    syncViewport();
    viewport.addEventListener('resize', syncViewport);
    viewport.addEventListener('scroll', syncViewport);
    return () => {
      viewport.removeEventListener('resize', syncViewport);
      viewport.removeEventListener('scroll', syncViewport);
    };
  }, [showAiAssistant]);
  if (!showAiAssistant) return null;
  return (
    <div ref={overlayRef} className="ai-assistant-overlay">
      <div className="ai-assistant-drawer" role="dialog" aria-modal="true" aria-label="ИИ Помощник" style={{backgroundColor:C.bgWhite}}>
        <div className="ai-assistant-header" style={{borderBottom:'1.5px solid '+C.border,backgroundColor:C.sidebar}}>
          <div><b style={{color:'white',fontSize:'15px'}}>🤖 ИИ Помощник</b><p style={{color:'rgba(255,255,255,0.5)',margin:'2px 0',fontSize:'12px'}}>Материалы, работы и данные вашей компании</p></div>
          <button type="button" className="ai-assistant-close" aria-label="Закрыть помощника" onClick={()=>setShowAiAssistant(false)} style={{backgroundColor:'transparent',border:'none',cursor:'pointer',color:'white'}}><X size={20}/></button>
        </div>
        <div className="ai-assistant-messages" role="log" aria-label="Переписка с помощником" aria-live="polite">
          {aiChat.length===0&&(<div style={{textAlign:'center',padding:'30px',color:C.textMuted}}><div style={{fontSize:'40px',marginBottom:'10px'}}>🏗️</div><b style={{color:C.text}}>Спросите меня!</b><div style={{display:'flex',flexDirection:'column',gap:'8px',marginTop:'16px'}}>{['Сколько цемента нужно для стяжки 50м2?','Нормы расхода штукатурки на 1м2?','Как рассчитать количество кирпича?','Какие СНиП для жилых домов?'].map(q=>(<button key={q} onClick={()=>setAiMessage(q)} style={{...btnG,fontSize:'12px',textAlign:'left',justifyContent:'flex-start'}}>{q}</button>))}</div></div>)}
          {aiChat.map((msg,i)=>(<div key={i} style={{display:'flex',justifyContent:msg.role==='user'?'flex-end':'flex-start'}}><div className="ai-assistant-bubble" style={{maxWidth:'85%',backgroundColor:msg.role==='user'?C.accent:C.bg,color:msg.role==='user'?'white':C.text,padding:'10px 14px',borderRadius:msg.role==='user'?'16px 16px 4px 16px':'16px 16px 16px 4px',border:'1.5px solid '+(msg.role==='user'?C.accent:C.border),fontSize:'13px',lineHeight:'1.5'}}>{msg.content}<div style={{fontSize:'10px',color:msg.role==='user'?'rgba(255,255,255,0.6)':C.textMuted,marginTop:'4px',textAlign:'right'}}>{msg.time}</div></div></div>))}
          {aiLoading&&<div style={{display:'flex',justifyContent:'flex-start'}}><div style={{backgroundColor:C.bg,padding:'10px 14px',borderRadius:'16px',border:'1.5px solid '+C.border,color:C.textSec,fontSize:'13px'}}>Думаю...</div></div>}
          <div ref={chatEndRef}/>
        </div>
        <div className="ai-assistant-composer" style={{borderTop:'1.5px solid '+C.border}}>
          <div style={{display:'flex',gap:'8px',minWidth:0}}><input className="ai-assistant-input" aria-label="Вопрос помощнику" maxLength={AI_MAX_MESSAGE_CHARS} placeholder="Задайте вопрос..." value={aiMessage} onChange={e=>setAiMessage(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.nativeEvent.isComposing&&!aiLoading){e.preventDefault();sendAiMessage();}}} style={{...inp,fontSize:undefined,marginBottom:0,flex:1,minWidth:0}} disabled={aiLoading}/><button type="button" aria-label="Отправить вопрос" onClick={sendAiMessage} disabled={aiLoading||!aiMessage.trim()} style={{...btnO,flex:'0 0 auto'}}>➤</button></div>
        </div>
      </div>
    </div>
  );
}
