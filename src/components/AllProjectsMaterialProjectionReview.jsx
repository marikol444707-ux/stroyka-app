import React from 'react';
import { ChevronDown, ChevronRight, GitCompareArrows, ShieldCheck } from 'lucide-react';
import { buildAllProjectsMaterialProjectionReview } from '../utils/materialProjectionDryRunUtils';

const requestReasonLabel = {
  legacy_aggregate_split: 'Старая объединённая позиция',
  material_not_in_projection: 'Нет в текущем расчёте',
  ambiguous_material_identity: 'Неоднозначное наименование',
  unit_mismatch: 'Не совпадает единица измерения',
  package_mismatch: 'Не совпадает пакет работ',
  missing_request_id: 'У заявки нет ID',
  ambiguous_project_identity: 'Неоднозначный объект',
  project_not_found: 'Объект заявки не найден',
  project_inactive: 'Объект заявки неактивен',
  project_identity_invalid: 'У объекта нет ID',
  conflicting_request_duplicates: 'Дубли заявки расходятся',
};

const REVIEW_PAGE_SIZE = 50;

const formatQuantity = (quantity, unit) => {
  const value = Number(quantity || 0);
  const formatted = Number.isFinite(value) ? value.toLocaleString('ru-RU', {maximumFractionDigits: 3}) : '0';
  return `${formatted}${unit ? ` ${unit}` : ''}`;
};

export default function AllProjectsMaterialProjectionReview({
  projects = [],
  projectIdentityCandidates = null,
  materialReconciliationRows,
  supplyRequests = [],
  parseSupplyItems,
  C,
  isMobile = false,
  canReviewSupplyRequests = true,
}) {
  const [expanded, setExpanded] = React.useState(false);
  const [reviewOnly, setReviewOnly] = React.useState(false);
  const [reviewPage, setReviewPage] = React.useState({signature: null, limit: REVIEW_PAGE_SIZE});
  const report = React.useMemo(() => {
    if (!expanded) return null;
    const requestData = canReviewSupplyRequests ? supplyRequests : [];
    return buildAllProjectsMaterialProjectionReview((projects || []).map(project => ({
      projectId: project?.id,
      projectName: project?.name,
      correctedRows: typeof materialReconciliationRows === 'function' ? materialReconciliationRows(project?.name) : [],
      requests: requestData,
    })), parseSupplyItems, (projectIdentityCandidates || projects || []).map(project => ({
      projectId: project?.id,
      projectName: project?.name,
    })), requestData);
  }, [canReviewSupplyRequests, expanded, materialReconciliationRows, parseSupplyItems, projectIdentityCandidates, projects, supplyRequests]);
  const summary = report?.summary || {};
  const visibleProjects = (report?.projects || []).filter(project => !reviewOnly || project.needsReview);
  const reviewItems = report?.reviewItems || [];
  const reviewSignature = JSON.stringify({
    summary,
    projects: (report?.projects || []).map(project => [
      project.projectId,
      project.projectName,
      project.projectionChanges,
      project.requestItemsNeedingReview,
      project.activeRequests,
      project.requestItems,
      project.requestItemsReady,
      project.needsReview,
    ]),
    reviewItems: reviewItems.map(item => [
      item.projectName,
      item.projectId,
      item.requestKey,
      item.itemIndex,
      item.reason,
      item.materialName,
      item.quantity,
      item.unit,
      item.workPackage,
      item.requestStatus,
      item.candidateNames || [],
      item.candidateProjectIds || [],
    ]),
  });
  const reviewLimit = reviewPage.signature === reviewSignature ? reviewPage.limit : REVIEW_PAGE_SIZE;
  const visibleReviewItems = reviewItems.slice(0, reviewLimit);

  React.useEffect(() => {
    if (!expanded) return;
    setReviewPage(current => (
      current.signature === reviewSignature
        ? current
        : {signature: reviewSignature, limit: REVIEW_PAGE_SIZE}
    ));
  }, [expanded, reviewSignature]);

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
          {canReviewSupplyRequests ? <>
            <span>Сметных заявок: {summary.activeRequests||0}</span>
            <span>Заявок проверить: {summary.requestsNeedingReview||0}</span>
            <span>Позиций заявок проверить: {summary.requestItemsNeedingReview||0}</span>
          </> : <span>Заявки: недоступны</span>}
        </div>
        <div>
          {visibleProjects.map(project => <div key={project.projectId||project.projectName} style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(auto-fit,minmax(120px,1fr))',gap:'8px',alignItems:'center',padding:'10px 0',borderBottom:'1px solid '+C.border,fontSize:'11px'}}>
            <b style={{color:C.text,overflowWrap:'anywhere'}}>{project.projectName}</b>
            <span style={{color:project.projectionChanges?C.warning:C.textSec}}>Расчёт: {project.projectionChanges}</span>
            <span style={{color:project.requestItemsNeedingReview?C.warning:C.textSec}}>Заявки: {project.requestItemsNeedingReview}</span>
            <b style={{color:project.needsReview?C.warning:C.success}}>{project.needsReview?'Проверить':'Готово'}</b>
          </div>)}
          {visibleProjects.length===0&&<p role="status" style={{color:C.success,fontSize:'11px',margin:'10px 0 0'}}>Объектов, требующих проверки, нет.</p>}
        </div>
        <div style={{marginTop:'14px',paddingTop:'12px',borderTop:'1px solid '+C.border}}>
          <div style={{display:'flex',justifyContent:'space-between',gap:'10px',alignItems:'baseline',flexWrap:'wrap'}}>
            <b style={{color:C.text,fontSize:'12px'}}>Список заявок на проверку</b>
            {canReviewSupplyRequests&&<span style={{color:C.textSec,fontSize:'10px'}}>Заявок: {summary.requestsNeedingReview||0} · позиций: {reviewItems.length}</span>}
          </div>
          {!canReviewSupplyRequests ? (
            <p role="status" style={{color:C.textSec,fontSize:'11px',margin:'8px 0 0'}}>Проверка заявок недоступна для этой роли.</p>
          ) : reviewItems.length===0 ? (
            <p role="status" style={{color:C.success,fontSize:'11px',margin:'8px 0 0'}}>Действующих заявок с устаревшими или неоднозначными позициями нет.</p>
          ) : (
            <div style={{marginTop:'8px'}}>
              {visibleReviewItems.map(item=><div data-testid="request-review-row" key={`${item.projectId??item.projectName}-${item.requestKey||item.requestId||'missing'}-${item.itemIndex}`} style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(auto-fit,minmax(180px,1fr))',gap:'8px',padding:'10px 0',borderBottom:'1px solid '+C.border,alignItems:'start'}}>
                <div style={{minWidth:0}}>
                  <span style={{display:'block',color:C.textSec,fontSize:'10px',overflowWrap:'anywhere'}}>Объект: {item.projectName||'Не указан'}</span>
                  <b style={{display:'block',color:C.text,fontSize:'11px',marginTop:'2px'}}>{item.requestId===null||item.requestId===undefined?'Заявка без ID':`Заявка #${item.requestId}`}</b>
                </div>
                <div style={{minWidth:0}}>
                  <b style={{display:'block',color:C.text,fontSize:'11px',overflowWrap:'anywhere'}}>{item.materialName}</b>
                  <span style={{display:'block',color:C.textSec,fontSize:'10px',marginTop:'2px',overflowWrap:'anywhere'}}>{formatQuantity(item.quantity,item.unit)}{item.workPackage?' · '+item.workPackage:''}</span>
                </div>
                <div style={{minWidth:0}}>
                  <span style={{display:'block',color:C.warning,fontSize:'10px',fontWeight:'700',overflowWrap:'anywhere'}}>{requestReasonLabel[item.reason]||item.reason}</span>
                  {(item.candidateNames||[]).length>0&&<span style={{display:'block',color:C.textSec,fontSize:'10px',marginTop:'2px',overflowWrap:'anywhere'}}>Сверить с: {(item.candidateNames||[]).join('; ')}</span>}
                  {(item.candidateProjectIds||[]).length>0&&<span style={{display:'block',color:C.textSec,fontSize:'10px',marginTop:'2px',overflowWrap:'anywhere'}}>Возможные объекты: {(item.candidateProjectIds||[]).map(id=>`#${id}`).join('; ')}</span>}
                </div>
                <span style={{color:C.textSec,fontSize:'10px',minWidth:0,overflowWrap:'anywhere'}}>{item.requestStatus}</span>
              </div>)}
              {visibleReviewItems.length<reviewItems.length&&<button
                type="button"
                aria-label="Показать ещё заявки на проверку"
                onClick={()=>setReviewPage({signature:reviewSignature,limit:reviewLimit+REVIEW_PAGE_SIZE})}
                style={{marginTop:'10px',padding:'7px 9px',border:'1px solid '+C.border,borderRadius:'6px',backgroundColor:C.bgWhite,color:C.text,fontSize:'10px',fontWeight:'700',cursor:'pointer'}}
              >Показать ещё ({Math.min(REVIEW_PAGE_SIZE,reviewItems.length-visibleReviewItems.length)})</button>}
            </div>
          )}
        </div>
      </div>}
    </section>
  );
}
