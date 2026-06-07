import React from 'react';
import CompanyChatMessageBubble from './CompanyChatMessageBubble';

export default function CompanyChatMessagesList({C, companyMessages, user, roleColor, fileSrc, setShowPhotoModal}) {
  return (
    <div style={{flex:1,overflowY:'auto',padding:'20px',display:'flex',flexDirection:'column',gap:'12px',backgroundColor:C.bg}}>
      {companyMessages.length===0&&<p style={{color:C.textMuted,textAlign:'center',margin:'auto'}}>Сообщений нет</p>}
      {companyMessages.map(msg=>(
        <CompanyChatMessageBubble
          key={msg.id}
          msg={msg}
          user={user}
          C={C}
          roleColor={roleColor}
          fileSrc={fileSrc}
          setShowPhotoModal={setShowPhotoModal}
        />
      ))}
    </div>
  );
}
