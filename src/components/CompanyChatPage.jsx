import React from 'react';
import CompanyChatMessagesList from './CompanyChatMessagesList';
import CompanyChatComposer from './CompanyChatComposer';

export default function CompanyChatPage({C, card, inp, btnO, companyMessages, user, roleColor, fileSrc, setShowPhotoModal, companyChatMessage, setCompanyChatMessage, uploadPhoto, sendCompanyChatMessage}) {
  return (
    <div>
      <h3 style={{color:C.text,marginBottom:'20px',fontSize:'16px',fontWeight:'700'}}>Общий чат</h3>
      <div style={{...card,padding:'0',overflow:'hidden',height:'calc(100vh - 200px)',display:'flex',flexDirection:'column'}}>
        <CompanyChatMessagesList C={C} companyMessages={companyMessages} user={user} roleColor={roleColor} fileSrc={fileSrc} setShowPhotoModal={setShowPhotoModal}/>
        <CompanyChatComposer C={C} inp={inp} btnO={btnO} companyChatMessage={companyChatMessage} setCompanyChatMessage={setCompanyChatMessage} uploadPhoto={uploadPhoto} sendCompanyChatMessage={sendCompanyChatMessage}/>
      </div>
    </div>
  );
}
