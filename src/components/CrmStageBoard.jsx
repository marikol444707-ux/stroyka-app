import React from 'react';
import { Building2, Edit2, Trash2 } from 'lucide-react';

export default function CrmStageBoard({C, card, btnG, btnR, crmStages, leads, saveLead, deleteLead, createProjectFromLead, setEditingItem, setNewLead, setShowForm}) {
  return (
    <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:'12px',overflowX:'auto'}}>
      {crmStages.map(stage=>(
        <div key={stage} style={{minWidth:'200px'}}>
          <div style={{padding:'8px 12px',backgroundColor:stage==='Отказ'?C.dangerLight:stage==='Договор'?C.successLight:C.bg,borderRadius:'8px',marginBottom:'10px',border:'1.5px solid '+(stage==='Отказ'?C.dangerBorder:stage==='Договор'?C.successBorder:C.border)}}>
            <b style={{color:stage==='Отказ'?C.danger:stage==='Договор'?C.success:C.text,fontSize:'12px'}}>{stage}</b>
            <span style={{color:C.textSec,fontSize:'11px',marginLeft:'6px'}}>{'('+leads.filter(l=>l.stage===stage).length+')'}</span>
          </div>
          {leads.filter(l=>l.stage===stage).map(lead=>(
            <div key={lead.id} style={{...card,padding:'12px',marginBottom:'8px',borderLeft:'3px solid '+C.accent}}>
              <b style={{color:C.text,fontSize:'13px'}}>{lead.name}</b>
              <p style={{color:C.textSec,margin:'3px 0',fontSize:'11px'}}>{lead.phone+(lead.email?' · '+lead.email:'')}</p>
              {lead.budget&&<p style={{color:C.success,margin:'2px 0',fontSize:'12px',fontWeight:'600'}}>{Number(lead.budget).toLocaleString()+' ₽'}</p>}
              <p style={{color:C.textMuted,margin:'2px 0',fontSize:'11px'}}>{lead.source}</p>
              <div style={{display:'flex',gap:'4px',marginTop:'8px',flexWrap:'wrap'}}>
                {crmStages.filter(s=>s!==stage).map(s=>(
                  <button key={s} onClick={()=>saveLead({...lead,stage:s})} style={{padding:'2px 8px',backgroundColor:C.bg,border:'1px solid '+C.border,borderRadius:'4px',cursor:'pointer',fontSize:'10px',color:C.textSec}}>→{s}</button>
                ))}
                {createProjectFromLead&&(
                  <button
                    onClick={()=>createProjectFromLead(lead)}
                    disabled={!!lead.projectId}
                    style={{...btnG,padding:'2px 6px',fontSize:'10px',opacity:lead.projectId ? .75 : 1,cursor:lead.projectId?'default':'pointer'}}
                    title={lead.projectId?'Объект уже создан':'Создать объект из заявки'}
                  >
                    <Building2 size={9}/>{lead.projectId?'Объект':'В объект'}
                  </button>
                )}
                <button onClick={()=>{setEditingItem(lead);setNewLead({...lead});setShowForm(true);}} style={{...btnG,padding:'2px 6px',fontSize:'10px'}}><Edit2 size={9}/></button>
                <button onClick={()=>deleteLead(lead.id)} style={{...btnR,padding:'2px 6px',fontSize:'10px'}}><Trash2 size={9}/></button>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
