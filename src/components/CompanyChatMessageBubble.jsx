import React from 'react';

export default function CompanyChatMessageBubble({msg, user, C, roleColor, fileSrc, setShowPhotoModal}) {
  const isMe = (msg.author_name||msg.author)===user.name;

  return (
    <div style={{display:'flex',justifyContent:isMe?'flex-end':'flex-start',alignItems:'flex-end',gap:'8px'}}>
      {!isMe&&(
        <div style={{width:'32px',height:'32px',borderRadius:'10px',backgroundColor:roleColor(msg.author_role||msg.role),display:'flex',alignItems:'center',justifyContent:'center',color:'white',fontWeight:'700',fontSize:'13px',flexShrink:0}}>
          {(msg.author_name||msg.author||'?').charAt(0)}
        </div>
      )}
      <div style={{maxWidth:'70%'}}>
        {!isMe&&<div style={{fontSize:'11px',fontWeight:'700',color:roleColor(msg.author_role||msg.role),marginBottom:'4px'}}>{msg.author_name||msg.author}</div>}
        <div style={{backgroundColor:isMe?C.accent:C.bgWhite,color:isMe?'white':C.text,padding:'10px 14px',borderRadius:isMe?'18px 18px 4px 18px':'18px 18px 18px 4px',border:'1.5px solid '+(isMe?C.accent:C.border),boxShadow:'0 1px 3px rgba(0,0,0,0.06)'}}>
          {msg.text&&<p style={{margin:0,fontSize:'14px',lineHeight:'1.5'}}>{msg.text}</p>}
          {msg.photo_url&&<img src={fileSrc(msg.photo_url)} alt='' onClick={()=>setShowPhotoModal(fileSrc(msg.photo_url))} style={{width:'200px',borderRadius:'8px',display:'block',marginTop:msg.text?'8px':'0',cursor:'pointer'}}/>}
        </div>
        <div style={{fontSize:'10px',color:C.textMuted,marginTop:'3px',textAlign:isMe?'right':'left'}}>
          {msg.created_at?new Date(msg.created_at).toLocaleTimeString('ru-RU'):''}
        </div>
      </div>
    </div>
  );
}
