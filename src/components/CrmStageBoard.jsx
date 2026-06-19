import React from 'react';
import { Building2, Edit2, Trash2 } from 'lucide-react';

export default function CrmStageBoard({C, card, btnG, btnR, crmStages, leads, saveLead, deleteLead, createProjectFromLead, setEditingItem, setNewLead, setShowForm, isMobile=false}) {
  return (
    <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(5,minmax(200px,1fr))',gap:isMobile?'14px':'12px',overflowX:isMobile?'visible':'auto',maxWidth:isMobile?'720px':undefined,margin:isMobile?'0 auto':undefined}}>
      {crmStages.map(stage=>(
        <div key={stage} style={{minWidth:isMobile?0:'200px',width:'100%'}}>
          <div style={{padding:isMobile?'10px 12px':'8px 12px',backgroundColor:stage==='Отказ'?C.dangerLight:stage==='Договор'?C.successLight:C.bg,borderRadius:'8px',marginBottom:'10px',border:'1.5px solid '+(stage==='Отказ'?C.dangerBorder:stage==='Договор'?C.successBorder:C.border),display:'flex',alignItems:'center',gap:'6px',flexWrap:'wrap'}}>
            <b style={{color:stage==='Отказ'?C.danger:stage==='Договор'?C.success:C.text,fontSize:isMobile?'13px':'12px',overflowWrap:'anywhere'}}>{stage}</b>
            <span style={{color:C.textSec,fontSize:'11px'}}>{'('+leads.filter(l=>l.stage===stage).length+')'}</span>
          </div>
          {leads.filter(l=>l.stage===stage).map(lead=>(
            <div key={lead.id} style={{...card,padding:isMobile?'14px':'12px',marginBottom:'8px',borderLeft:'3px solid '+C.accent,overflow:'hidden'}}>
              <b style={{color:C.text,fontSize:isMobile?'14px':'13px',display:'block',overflowWrap:'anywhere'}}>{lead.name}</b>
              <p style={{color:C.textSec,margin:'4px 0',fontSize:isMobile?'12px':'11px',overflowWrap:'anywhere'}}>{lead.phone+(lead.email?' · '+lead.email:'')}</p>
              {lead.budget&&<p style={{color:C.success,margin:'2px 0',fontSize:'12px',fontWeight:'600'}}>{Number(lead.budget).toLocaleString()+' ₽'}</p>}
              <p style={{color:C.textMuted,margin:'2px 0',fontSize:'11px',overflowWrap:'anywhere'}}>{lead.source}</p>
              <div style={{display:'flex',gap:isMobile?'6px':'4px',marginTop:'8px',flexWrap:'wrap'}}>
                {crmStages.filter(s=>s!==stage).map(s=>(
                  <button key={s} onClick={()=>saveLead({...lead,stage:s})} style={{padding:isMobile?'7px 9px':'2px 8px',backgroundColor:C.bg,border:'1px solid '+C.border,borderRadius:isMobile?'8px':'4px',cursor:'pointer',fontSize:isMobile?'11px':'10px',color:C.textSec,flex:isMobile?'1 1 120px':'0 0 auto',whiteSpace:'normal',minHeight:isMobile?'34px':undefined}}>→{s}</button>
                ))}
                {createProjectFromLead&&(
                  <button
                    onClick={()=>createProjectFromLead(lead)}
                    disabled={!!lead.projectId}
                    style={{...btnG,padding:isMobile?'7px 9px':'2px 6px',fontSize:isMobile?'11px':'10px',opacity:lead.projectId ? .75 : 1,cursor:lead.projectId?'default':'pointer',flex:isMobile?'1 1 120px':'0 0 auto',justifyContent:'center',minHeight:isMobile?'34px':undefined}}
                    title={lead.projectId?'Объект уже создан':'Создать объект из заявки'}
                  >
                    <Building2 size={9}/>{lead.projectId?'Объект':'В объект'}
                  </button>
                )}
                <button onClick={()=>{setEditingItem(lead);setNewLead({...lead});setShowForm(true);}} style={{...btnG,padding:isMobile?'7px 9px':'2px 6px',fontSize:isMobile?'11px':'10px',minWidth:isMobile?'38px':undefined,justifyContent:'center'}}><Edit2 size={9}/></button>
                <button onClick={()=>deleteLead(lead.id)} style={{...btnR,padding:isMobile?'7px 9px':'2px 6px',fontSize:isMobile?'11px':'10px',minWidth:isMobile?'38px':undefined,justifyContent:'center'}}><Trash2 size={9}/></button>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
