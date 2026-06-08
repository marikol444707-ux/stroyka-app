import React from 'react';
import { Archive, ChevronDown, ChevronUp, Edit2 } from 'lucide-react';

function ProjectCardHeader({
  C,
  btnG,
  badge,
  project,
  statusColors,
  isOpen,
  total,
  canSeeFinance,
  canManage,
  onToggle,
  onEdit,
  onArchiveToggle,
}) {
  const statusStyle = statusColors[project.status] || statusColors['Планирование'];

  return (
    <div style={{padding:'14px 16px',cursor:'pointer'}} onClick={onToggle}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
        <div style={{flex:1}}>
          <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'6px'}}>
            <b style={{fontSize:'15px',color:C.text}}>{project.name}</b>
            <span style={badge(statusStyle[0],statusStyle[1],statusStyle[2])}>{project.status}</span>
          </div>
          <div style={{display:'flex',gap:'15px',flexWrap:'wrap'}}>
            <span style={{fontSize:'12px',color:C.textSec}}>{'👤 '+project.client}</span>
            {project.floors>1&&<span style={{fontSize:'12px',color:C.textSec}}>{'🏢 '+project.floors+' эт.'}</span>}
            {project.liters&&<span style={{fontSize:'12px',color:C.textSec}}>{'🔤 Лит. '+project.liters}</span>}
            {project.deadline&&<span style={{fontSize:'12px',color:C.textSec}}>{'📅 '+project.deadline}</span>}
            {canSeeFinance&&<span style={{fontSize:'12px',color:C.textSec}}>{'💰 '+total.toLocaleString()+' / '+(project.budget||0).toLocaleString()+' ₽'}</span>}
          </div>
        </div>
        <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
          {canManage&&<button onClick={e=>{e.stopPropagation();onEdit();}} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><Edit2 size={11}/></button>}
          {canManage&&(
            <button
              onClick={e=>{e.stopPropagation();onArchiveToggle();}}
              style={{...btnG,padding:'5px 10px',fontSize:'11px'}}
              title={project.archived?'Вернуть из архива':'Закрыть объект в архив'}
            >
              <Archive size={11}/>{project.archived?'↩':''}
            </button>
          )}
          {isOpen?<ChevronUp size={18} color={C.textMuted}/>:<ChevronDown size={18} color={C.textMuted}/>}
        </div>
      </div>
    </div>
  );
}

export default ProjectCardHeader;
