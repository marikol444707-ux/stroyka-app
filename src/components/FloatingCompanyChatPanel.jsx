import React from 'react';
import { Camera, FileText, MessageSquare, X } from 'lucide-react';

export default function FloatingCompanyChatPanel({
  showChatPanel,
  setShowChatPanel,
  companyMessages,
  user,
  companyChatInput,
  setCompanyChatInput,
  sendCompanyChatMessage,
  uploadPhoto,
}) {
  if (!showChatPanel) return null;
  const send = () => {
    if (companyChatInput?.trim()) {
      sendCompanyChatMessage(companyChatInput);
      setCompanyChatInput('');
    }
  };

  return (
    <>
      <div onMouseDown={e=>{e.preventDefault();setShowChatPanel(false);}} style={{position:'fixed',top:0,left:0,right:0,bottom:'60px',backgroundColor:'rgba(0,0,0,0.5)',zIndex:399}}/>
      <div style={{position:'fixed',bottom:'70px',right:'12px',width:'340px',height:'460px',backgroundColor:'#0f172a',borderRadius:'16px',zIndex:400,display:'flex',flexDirection:'column',boxShadow:'0 8px 32px rgba(0,0,0,0.5)',border:'1px solid rgba(148,163,184,0.18)'}}>
        <div style={{padding:'16px',borderBottom:'1px solid rgba(148,163,184,0.18)',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <b style={{color:'#f8fafc',fontSize:'16px'}}>💬 Чат</b>
          <button onClick={()=>setShowChatPanel(false)} style={{background:'none',border:'none',cursor:'pointer',color:'#94a3b8'}}><X size={20}/></button>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'12px',display:'flex',flexDirection:'column',gap:'8px'}}>
          {companyMessages.slice(-20).map((msg,i)=>(
            <div key={i} style={{display:'flex',justifyContent:(msg.author_name||msg.author)===user.name?'flex-end':'flex-start'}}>
              <div style={{maxWidth:'80%',padding:'10px 14px',borderRadius:(msg.author_name||msg.author)===user.name?'16px 16px 4px 16px':'16px 16px 16px 4px',backgroundColor:(msg.author_name||msg.author)===user.name?'#ea580c':'rgba(30,41,59,0.8)',color:'#f8fafc',fontSize:'13px',lineHeight:'1.5'}}>
                {(msg.author_name||msg.author)!==user.name&&<div style={{fontSize:'11px',color:'#94a3b8',marginBottom:'4px',fontWeight:'600'}}>{msg.author_name||msg.author}</div>}
                {msg.text}
                <div style={{fontSize:'10px',color:'rgba(255,255,255,0.5)',marginTop:'4px',textAlign:'right'}}>{msg.time}</div>
              </div>
            </div>
          ))}
          {companyMessages.length===0&&<div style={{textAlign:'center',color:'#94a3b8',padding:'30px',fontSize:'14px'}}>Нет сообщений</div>}
        </div>
        <div style={{padding:'12px',borderTop:'1px solid rgba(148,163,184,0.18)',display:'flex',gap:'8px'}}>
          <label style={{padding:'8px',background:'rgba(30,41,59,0.8)',border:'1px solid rgba(148,163,184,0.18)',borderRadius:'10px',cursor:'pointer',display:'flex',alignItems:'center'}}>
            <Camera size={16} color='#94a3b8'/>
            <input type='file' accept='image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{context:'company-chat'});sendCompanyChatMessage('[Фото]',url);}}}/>
          </label>
          <label style={{padding:'8px',background:'rgba(30,41,59,0.8)',border:'1px solid rgba(148,163,184,0.18)',borderRadius:'10px',cursor:'pointer',display:'flex',alignItems:'center'}}>
            <FileText size={16} color='#94a3b8'/>
            <input type='file' accept='.pdf,.doc,.docx' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){sendCompanyChatMessage('[Документ] '+e.target.files[0].name,'');}}}/>
          </label>
          <input placeholder="Сообщение..." value={companyChatInput||''} onChange={e=>setCompanyChatInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&companyChatInput?.trim()) send();}} style={{flex:1,padding:'10px 14px',backgroundColor:'rgba(30,41,59,0.8)',border:'1px solid rgba(148,163,184,0.18)',borderRadius:'12px',color:'#f8fafc',fontSize:'13px',outline:'none'}}/>
          <button onClick={send} style={{padding:'10px 16px',backgroundColor:'#ea580c',border:'none',borderRadius:'12px',color:'white',cursor:'pointer'}}><MessageSquare size={16}/></button>
        </div>
      </div>
    </>
  );
}
