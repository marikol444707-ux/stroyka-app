import React from 'react';
import { ChevronDown, ChevronRight, GitCompareArrows, ShieldCheck } from 'lucide-react';
import { buildAllProjectsMaterialProjectionReview } from '../utils/materialProjectionDryRunUtils';

export default function AllProjectsMaterialProjectionReview({
  projects = [],
  materialReconciliationRows,
  supplyRequests = [],
  parseSupplyItems,
  C,
  isMobile = false,
}) {
  const [expanded, setExpanded] = React.useState(false);
  const [reviewOnly, setReviewOnly] = React.useState(false);
  const report = React.useMemo(() => {
    if (!expanded) return null;
    return buildAllProjectsMaterialProjectionReview((projects || []).map(project => ({
      projectId: project.id,
      projectName: project.name,
      correctedRows: typeof materialReconciliationRows === 'function' ? materialReconciliationRows(project.name) : [],
      requests: supplyRequests,
    })), parseSupplyItems);
  }, [expanded, materialReconciliationRows, parseSupplyItems, projects, supplyRequests]);
  const summary = report?.summary || {};
  const visibleProjects = (report?.projects || []).filter(project => !reviewOnly || project.needsReview);

  return (
    <section aria-label="Проверка всех объектов" style={{borderTop:'1px solid '+C.border,borderBottom:'1px solid '+C.border,marginBottom:'14px',padding:'10px 0'}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'10px',flexWrap:'wrap'}}>
        <div style={{display:'flex',alignItems:'center',gap:'9px',minWidth:0}}>
          <GitCompareArrows size={18} color={expanded && summary.projectsNeedingReview ? C.warning : C.info}/>
          <div style={{minWidth:0}}>
            <b style={{display:'block',color:C.text,fontSize:'13px'}}>Проверка всех объектов</b>
            <span style={{display:'block',color:C.textSec,fontSize:'11px',marginTop:'2px'}}>
              {expanded
                ? `Объектов: ${summary.projects || 0} · требуют проверки: ${summary.projectsNeedingReview || 0}`
                : `Активных объектов: ${(projects || []).length}`}
            </span>
          </div>
        </div>
        <button
          type="button"
          aria-expanded={expanded}
          aria-label={expanded ? 'Закрыть проверку всех объектов' : 'Открыть проверку всех объектов'}
          onClick={()=>setExpanded(value=>!value)}
          style={{display:'inline-flex',alignItems:'center',gap:'6px',padding:'7px 9px',border:'1px solid '+C.border,borderRadius:'6px',backgroundColor:C.bgWhite,color:C.text,fontSize:'11px',fontWeight:'700',cursor:'pointer'}}
        >
          {expanded?<ChevronDown size={14}/>:<ChevronRight size={14}/>} {expanded?'Скрыть':'Проверить'}
        </button>
      </div>

      {expanded && <div style={{marginTop:'10px'}}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'10px',padding:'8px 0',flexWrap:'wrap'}}>
          <div style={{display:'flex',alignItems:'center',gap:'7px',color:C.success,fontSize:'11px',fontWeight:'700'}}>
            <ShieldCheck size={15}/><span>Только просмотр</span>
            <span style={{color:C.textSec,fontWeight:'500'}}>Данные не изменяются.</span>
          </div>
          <button
            type="button"
            aria-pressed={reviewOnly}
            aria-label="Показать только объекты, требующие проверки"
            onClick={()=>setReviewOnly(value=>!value)}
            style={{padding:'6px 9px',border:'1px solid '+(reviewOnly?C.warning:C.border),borderRadius:'6px',backgroundColor:reviewOnly?C.warningLight:C.bgWhite,color:reviewOnly?C.warning:C.text,fontSize:'10px',fontWeight:'700',cursor:'pointer'}}
          >
            Требует проверки
          </button>
        </div>
        <div style={{display:'flex',gap:'12px',flexWrap:'wrap',padding:'8px 0 10px',fontSize:'11px',color:C.textSec,borderBottom:'1px solid '+C.border}}>
          <b style={{color:summary.projectsNeedingReview?C.warning:C.success}}>Объектов проверить: {summary.projectsNeedingReview||0}</b>
          <span>Изменений расчёта: {summary.projectionChanges||0}</span>
          <span>Активных заявок: {summary.activeRequests||0}</span>
          <span>Позиций заявок проверить: {summary.requestItemsNeedingReview||0}</span>
        </div>
        <div>
          {visibleProjects.map(project => <div key={project.projectId||project.projectName} style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'minmax(180px,1.5fr) repeat(3,minmax(110px,.7fr))',gap:'8px',alignItems:'center',padding:'10px 0',borderBottom:'1px solid '+C.border,fontSize:'11px'}}>
            <b style={{color:C.text,overflowWrap:'anywhere'}}>{project.projectName}</b>
            <span style={{color:project.projectionChanges?C.warning:C.textSec}}>Расчёт: {project.projectionChanges}</span>
            <span style={{color:project.requestItemsNeedingReview?C.warning:C.textSec}}>Заявки: {project.requestItemsNeedingReview}</span>
            <b style={{color:project.needsReview?C.warning:C.success}}>{project.needsReview?'Проверить':'Готово'}</b>
          </div>)}
          {visibleProjects.length===0&&<p role="status" style={{color:C.success,fontSize:'11px',margin:'10px 0 0'}}>Объектов, требующих проверки, нет.</p>}
        </div>
      </div>}
    </section>
  );
}
