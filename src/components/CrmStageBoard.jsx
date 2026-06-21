import React from 'react';
import { Building2, Edit2, Trash2 } from 'lucide-react';

export default function CrmStageBoard({C, card, btnG, btnR, crmStages, leads, saveLead, deleteLead, createProjectFromLead, setEditingItem, setNewLead, setShowForm, isMobile=false}) {
  const stageLeads = (stage) => (leads || []).filter(l => l.stage === stage);
  const stageBg = (stage) => stage === 'Отказ' ? C.dangerLight : stage === 'Договор' ? C.successLight : C.bg;
  const stageBorder = (stage) => stage === 'Отказ' ? C.dangerBorder : stage === 'Договор' ? C.successBorder : C.border;
  const stageText = (stage) => stage === 'Отказ' ? C.danger : stage === 'Договор' ? C.success : C.text;
  const editLead = (lead) => {
    setEditingItem(lead);
    setNewLead({...lead});
    setShowForm(true);
  };

  if (isMobile) {
    return (
      <div style={{display:'grid',gridTemplateColumns:'1fr',gap:'14px',maxWidth:'720px',margin:'0 auto'}}>
        {crmStages.map(stage => {
          const items = stageLeads(stage);
          return (
            <section key={stage} style={{...card,padding:'12px',overflow:'hidden'}}>
              <div style={{padding:'10px 12px',backgroundColor:stageBg(stage),borderRadius:'8px',marginBottom:'10px',border:'1.5px solid '+stageBorder(stage),display:'flex',alignItems:'center',justifyContent:'space-between',gap:'8px'}}>
                <b style={{color:stageText(stage),fontSize:'13px',overflowWrap:'anywhere'}}>{stage}</b>
                <span style={{color:C.textSec,fontSize:'11px',flex:'0 0 auto'}}>{items.length}</span>
              </div>
              {items.length === 0 && (
                <div style={{padding:'12px',border:'1px dashed '+C.border,borderRadius:'8px',color:C.textMuted,fontSize:'12px'}}>
                  Лидов нет
                </div>
              )}
              {items.map(lead => (
                <article key={lead.id} style={{padding:'12px',marginBottom:'10px',borderLeft:'3px solid '+C.accent,backgroundColor:C.bg,borderRadius:'8px',border:'1px solid '+C.border,overflow:'hidden'}}>
                  <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'8px'}}>
                    <b style={{color:C.text,fontSize:'14px',lineHeight:1.25,display:'block',overflowWrap:'anywhere'}}>{lead.name || 'Без названия'}</b>
                    {lead.projectId && (
                      <span style={{color:C.success,fontSize:'10px',fontWeight:700,backgroundColor:C.successLight,border:'1px solid '+C.successBorder,borderRadius:'999px',padding:'3px 7px',whiteSpace:'nowrap'}}>
                        Объект
                      </span>
                    )}
                  </div>
                  <p style={{color:C.textSec,margin:'6px 0 0',fontSize:'12px',lineHeight:1.35,overflowWrap:'anywhere'}}>
                    {[lead.phone, lead.email].filter(Boolean).join(' · ') || 'Контакт не указан'}
                  </p>
                  {lead.source && (
                    <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px',lineHeight:1.35,overflowWrap:'anywhere'}}>Источник: {lead.source}</p>
                  )}
                  {lead.budget && (
                    <p style={{color:C.success,margin:'6px 0 0',fontSize:'13px',fontWeight:700}}>{Number(lead.budget).toLocaleString()} ₽</p>
                  )}
                  <label style={{display:'block',color:C.textMuted,fontSize:'11px',fontWeight:700,margin:'12px 0 5px'}}>Стадия</label>
                  <select
                    value={stage}
                    onChange={e => {
                      if (e.target.value !== stage) saveLead({...lead, stage: e.target.value});
                    }}
                    style={{width:'100%',boxSizing:'border-box',padding:'10px 12px',borderRadius:'8px',border:'1.5px solid '+C.border,backgroundColor:C.bgCard,color:C.text,fontSize:'13px',minHeight:'42px'}}
                  >
                    {crmStages.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <div style={{display:'grid',gridTemplateColumns:createProjectFromLead?'1fr 44px 44px':'44px 44px',gap:'8px',marginTop:'10px',alignItems:'stretch'}}>
                    {createProjectFromLead && (
                      <button
                        onClick={() => createProjectFromLead(lead)}
                        disabled={!!lead.projectId}
                        style={{...btnG,padding:'9px 10px',fontSize:'12px',opacity:lead.projectId ? .75 : 1,cursor:lead.projectId?'default':'pointer',justifyContent:'center',minHeight:'40px'}}
                        title={lead.projectId?'Объект уже создан':'Создать объект из заявки'}
                      >
                        <Building2 size={14}/>{lead.projectId?'Объект создан':'В объект'}
                      </button>
                    )}
                    <button onClick={() => editLead(lead)} style={{...btnG,padding:'9px 10px',fontSize:'12px',minWidth:'44px',justifyContent:'center',minHeight:'40px'}} title="Редактировать"><Edit2 size={14}/></button>
                    <button onClick={() => deleteLead(lead.id)} style={{...btnR,padding:'9px 10px',fontSize:'12px',minWidth:'44px',justifyContent:'center',minHeight:'40px'}} title="Удалить"><Trash2 size={14}/></button>
                  </div>
                </article>
              ))}
            </section>
          );
        })}
      </div>
    );
  }

  return (
    <div style={{display:'grid',gridTemplateColumns:'repeat(5,minmax(200px,1fr))',gap:'12px',overflowX:'auto'}}>
      {crmStages.map(stage=>(
        <div key={stage} style={{minWidth:'200px',width:'100%'}}>
          <div style={{padding:'8px 12px',backgroundColor:stageBg(stage),borderRadius:'8px',marginBottom:'10px',border:'1.5px solid '+stageBorder(stage),display:'flex',alignItems:'center',gap:'6px',flexWrap:'wrap'}}>
            <b style={{color:stageText(stage),fontSize:'12px',overflowWrap:'anywhere'}}>{stage}</b>
            <span style={{color:C.textSec,fontSize:'11px'}}>{'('+stageLeads(stage).length+')'}</span>
          </div>
          {stageLeads(stage).map(lead=>(
            <div key={lead.id} style={{...card,padding:'12px',marginBottom:'8px',borderLeft:'3px solid '+C.accent,overflow:'hidden'}}>
              <b style={{color:C.text,fontSize:'13px',display:'block',overflowWrap:'anywhere'}}>{lead.name}</b>
              <p style={{color:C.textSec,margin:'4px 0',fontSize:'11px',overflowWrap:'anywhere'}}>{lead.phone+(lead.email?' · '+lead.email:'')}</p>
              {lead.budget&&<p style={{color:C.success,margin:'2px 0',fontSize:'12px',fontWeight:'600'}}>{Number(lead.budget).toLocaleString()+' ₽'}</p>}
              <p style={{color:C.textMuted,margin:'2px 0',fontSize:'11px',overflowWrap:'anywhere'}}>{lead.source}</p>
              <div style={{display:'flex',gap:'4px',marginTop:'8px',flexWrap:'wrap'}}>
                {crmStages.filter(s=>s!==stage).map(s=>(
                  <button key={s} onClick={()=>saveLead({...lead,stage:s})} style={{padding:'2px 8px',backgroundColor:C.bg,border:'1px solid '+C.border,borderRadius:'4px',cursor:'pointer',fontSize:'10px',color:C.textSec,flex:'0 0 auto',whiteSpace:'normal'}}>→{s}</button>
                ))}
                {createProjectFromLead&&(
                  <button
                    onClick={()=>createProjectFromLead(lead)}
                    disabled={!!lead.projectId}
                    style={{...btnG,padding:'2px 6px',fontSize:'10px',opacity:lead.projectId ? .75 : 1,cursor:lead.projectId?'default':'pointer',flex:'0 0 auto',justifyContent:'center'}}
                    title={lead.projectId?'Объект уже создан':'Создать объект из заявки'}
                  >
                    <Building2 size={9}/>{lead.projectId?'Объект':'В объект'}
                  </button>
                )}
                <button onClick={()=>editLead(lead)} style={{...btnG,padding:'2px 6px',fontSize:'10px',justifyContent:'center'}}><Edit2 size={9}/></button>
                <button onClick={()=>deleteLead(lead.id)} style={{...btnR,padding:'2px 6px',fontSize:'10px',justifyContent:'center'}}><Trash2 size={9}/></button>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
