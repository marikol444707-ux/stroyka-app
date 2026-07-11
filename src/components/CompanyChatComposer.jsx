import React from 'react';
import { Upload } from 'lucide-react';

export default function CompanyChatComposer({C, inp, btnO, companyChatMessage, setCompanyChatMessage, uploadPhoto, sendCompanyChatMessage}) {
  return (
    <div style={{padding:'14px 16px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bgWhite}}>
      <div style={{display:'flex',gap:'8px',alignItems:'flex-end'}}>
        <label style={{cursor:'pointer',backgroundColor:C.bgGray,padding:'10px',borderRadius:'10px',border:'1.5px solid '+C.border,display:'flex',alignItems:'center'}}>
          <Upload size={18} color={C.textSec}/>
          <input type="file" accept="image/*" style={{display:'none'}} onChange={async e=>{
            if(e.target.files[0]){
              const url = await uploadPhoto(e.target.files[0],{context:'company-chat',projectScoped:false});
              sendCompanyChatMessage('',url);
            }
          }}/>
        </label>
        <textarea placeholder="Написать..." value={companyChatMessage} onChange={e=>setCompanyChatMessage(e.target.value)} onKeyDown={e=>{
          if(e.key==='Enter'&&!e.shiftKey){
            e.preventDefault();
            sendCompanyChatMessage(companyChatMessage,'');
          }
        }} style={{...inp,marginBottom:'0',resize:'none',height:'55px',flex:1,fontSize:'14px'}}/>
        <button onClick={()=>sendCompanyChatMessage(companyChatMessage,'')} style={{...btnO,padding:'14px 22px',alignSelf:'flex-start'}}>➤</button>
      </div>
    </div>
  );
}
