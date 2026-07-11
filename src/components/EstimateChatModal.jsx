import React from 'react';

export default function EstimateChatModal({
  showEstimateChat,
  setShowEstimateChat,
  selectedEstimate,
  C,
  card,
  inp,
  btnG,
  btnO,
  isMobile,
  darkMode,
  clearEstimateChatHistory,
  estimateChatMessages,
  estimateChatLoading,
  estimateChatInput,
  setEstimateChatInput,
  sendEstimateChatMessage,
}) {
  if (!showEstimateChat || !selectedEstimate) return null;

  const clearChat = async () => {
    if (window.confirm('Очистить историю чата?')) {
      await clearEstimateChatHistory();
    }
  };

  return (
    <div onClick={()=>setShowEstimateChat(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:650,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal estimate-chat-modal' style={{...card,padding:0,width:'640px',height:'700px',margin:isMobile?'12px':'20px',display:'flex',flexDirection:'column',overflow:'hidden'}}>
        <div style={{padding:'14px 18px',backgroundColor:'#0ea5e9',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
            <span style={{fontSize:'22px'}}>💬</span>
            <div>
              <b style={{color:'white',fontSize:'14px',display:'block'}}>Чат по смете</b>
              <p style={{color:'rgba(255,255,255,0.85)',fontSize:'11px',margin:0}}>{selectedEstimate.name}</p>
            </div>
          </div>
          <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
            <button disabled={estimateChatLoading} onClick={clearChat} style={{background:'transparent',border:'1px solid rgba(255,255,255,0.4)',color:'white',cursor:estimateChatLoading?'not-allowed':'pointer',opacity:estimateChatLoading?0.6:1,padding:'4px 10px',borderRadius:'6px',fontSize:'11px'}}>🗑️ Очистить</button>
            <button onClick={()=>setShowEstimateChat(false)} style={{background:'none',border:'none',cursor:'pointer',color:'white',fontSize:'22px',padding:'0 6px'}}>×</button>
          </div>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'16px',display:'flex',flexDirection:'column',gap:'10px',backgroundColor:C.bg}}>
          {estimateChatMessages.length===0&&!estimateChatLoading&&(
            <div style={{textAlign:'center',padding:'30px',color:C.textMuted}}>
              <div style={{fontSize:'40px',marginBottom:'10px'}}>💬</div>
              <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'8px'}}>Задайте вопрос по смете</b>
              <p style={{fontSize:'12px',marginBottom:'14px'}}>ИИ помнит контекст этой сметы и предыдущие вопросы</p>
              <div style={{display:'flex',flexDirection:'column',gap:'6px',maxWidth:'420px',margin:'0 auto'}}>
                {['Какая самая дорогая позиция?','А если убрать раздел 5?','Чем заменить дорогие материалы?','Помоги объяснить клиенту почему смета подорожала'].map(q=>(
                  <button key={q} onClick={()=>setEstimateChatInput(q)} style={{...btnG,fontSize:'12px',textAlign:'left',justifyContent:'flex-start',padding:'8px 12px'}}>💭 {q}</button>
                ))}
              </div>
            </div>
          )}
          {estimateChatMessages.map((m,i)=>(
            <div key={m.id||i} style={{display:'flex',justifyContent:m.role==='user'?'flex-end':'flex-start'}}>
              <div style={{maxWidth:isMobile?'92%':'85%',padding:'12px 16px',borderRadius:m.role==='user'?'14px 14px 4px 14px':'14px 14px 14px 4px',backgroundColor:m.role==='user'?C.accent:(darkMode?'#f8fafc':C.bgWhite),color:m.role==='user'?'white':(darkMode?'#0f172a':C.text),fontSize:'14px',lineHeight:'1.6',boxShadow:'0 1px 3px rgba(0,0,0,0.10)',border:m.role==='user'?'none':'1.5px solid '+(darkMode?'#cbd5e1':C.border),whiteSpace:'pre-wrap'}}>{m.content}</div>
            </div>
          ))}
          {estimateChatLoading&&(<div style={{display:'flex',justifyContent:'flex-start'}}><div style={{padding:'12px 16px',borderRadius:'14px 14px 14px 4px',backgroundColor:darkMode?'#f8fafc':C.bgWhite,border:'1.5px solid '+(darkMode?'#cbd5e1':C.border),fontSize:'14px',color:darkMode?'#334155':C.textSec}}>⏳ Думаю над вопросом…</div></div>)}
        </div>
        <div style={{padding:'12px 14px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bgWhite,display:'flex',gap:'8px'}}>
          <input value={estimateChatInput} onChange={e=>setEstimateChatInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendEstimateChatMessage();}}} placeholder='Спросите по смете... (Enter — отправить)' disabled={estimateChatLoading} style={{...inp,marginBottom:0,flex:1,fontSize:'13px'}}/>
          <button disabled={estimateChatLoading||!estimateChatInput.trim()} onClick={sendEstimateChatMessage} style={{...btnO,padding:'10px 16px'}}>➤</button>
        </div>
      </div>
    </div>
  );
}
