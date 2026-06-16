import React from 'react';
import { Bot, Check, Plus, ShoppingCart } from 'lucide-react';
import MaterialNormCoverageHeader from './MaterialNormCoverageHeader';
import MaterialNormCoverageSummaryBadges from './MaterialNormCoverageSummaryBadges';

export default function MaterialNormCoveragePanel({
  C,
  badge,
  btnB,
  btnG,
  btnGr,
  btnO,
  btnState,
  card,
  inp,
  isMobile,
  projectOptions,
  selectedProject,
  setMaterialNormCoverageProject,
  rows,
  displayRows,
  visibleCoverageRows,
  hiddenCoverageRows,
  coverageKey,
  setMobileExpandedRenderLists,
  canEditMaterialNorms,
  canCreateSupplyRequestFromNorm,
  materialNormCanCreateSupply,
  materialNormSupplyRequestExists,
  materialNormCoverageMeta,
  materialNormCoverageComment,
  fmtMeasure,
  buildMaterialNormCoverageContent,
  showPreview,
  exportToExcel,
  materialNormCoverageExportRows,
  createBatchSupplyRequestFromNormCoverage,
  createSupplyRequestFromNormCoverage,
  addEstimateMaterialFromCoverage,
  markEstimateWorkNoMaterialFromCoverage,
  createMaterialNormCoverageTask,
  saveMaterialNormOverrideFromCoverage
}) {
  const okCount=rows.filter(r=>['Норма применена','Поправка объекта','Поправка сметы'].includes(r.status)).length;
  const skippedCount=rows.filter(r=>r.status==='Норма не нужна').length;
  const missingCount=rows.filter(r=>r.status==='Нет нормы').length;
  const unlinkedCount=rows.filter(r=>r.status==='Материал без работы').length;
  const shortageCount=rows.filter(r=>r.status==='Нехватка материала по норме').length;
  const invalidQtyCount=rows.filter(r=>r.status==='Некорректное количество').length;
  const zeroQtyCount=rows.filter(r=>r.status==='Материал без количества').length;
  const infoCount=rows.filter(r=>r.status==='Нет материала в смете').length;
  const canEdit = canEditMaterialNorms();
  const canCreateSupply = canCreateSupplyRequestFromNorm();

  return (
    <div style={{...card,padding:'14px',marginBottom:'16px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
      <MaterialNormCoverageHeader
        C={C}
        inp={inp}
        btnB={btnB}
        btnG={btnG}
        btnO={btnO}
        btnState={btnState}
        isMobile={isMobile}
        projectOptions={projectOptions}
        selectedProject={selectedProject}
        setMaterialNormCoverageProject={setMaterialNormCoverageProject}
        rows={rows}
        showCreateBatchSupply={canCreateSupply}
        canCreateBatchSupply={rows.some(r=>materialNormCanCreateSupply(r)&&!materialNormSupplyRequestExists(r))}
        onPrint={()=>showPreview(buildMaterialNormCoverageContent(selectedProject),'Смета по нормам — '+selectedProject)}
        onExport={()=>exportToExcel(materialNormCoverageExportRows(rows),'Смета_по_нормам_'+selectedProject)}
        onCreateBatchSupply={()=>createBatchSupplyRequestFromNormCoverage(rows)}
      />
      <MaterialNormCoverageSummaryBadges
        C={C}
        badge={badge}
        okCount={okCount}
        skippedCount={skippedCount}
        missingCount={missingCount}
        unlinkedCount={unlinkedCount}
        shortageCount={shortageCount}
        invalidQtyCount={invalidQtyCount}
        zeroQtyCount={zeroQtyCount}
        infoCount={infoCount}
        totalRows={rows.length}
      />
      {rows.length>0?<div style={{display:'grid',gap:'7px',maxHeight:'420px',overflowY:'auto',paddingRight:'2px'}}>
        {visibleCoverageRows.map(r=>{const meta=materialNormCoverageMeta(r.status);return(<div key={r.key} style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'minmax(260px,1.6fr) minmax(220px,1fr) 170px auto',gap:'10px',alignItems:'center',padding:'10px 11px',borderRadius:'9px',border:'1px solid '+C.border,backgroundColor:C.bg}}>
          <div style={{minWidth:0}}>
            <span style={badge(meta.color,meta.bg,meta.border)}>{r.status}</span>
            <b style={{display:'block',color:C.text,fontSize:'12px',marginTop:'5px',overflow:'hidden',textOverflow:'ellipsis'}}>{r.workName}</b>
            <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'11px'}}>{r.packageName+' · '+r.sectionName+' · '+fmtMeasure(r.workQty,r.workUnit)}</p>
          </div>
          <div style={{minWidth:0}}>
            <span style={{color:C.textMuted,fontSize:'10px',textTransform:'uppercase'}}>Материал / норма</span>
            <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'12px',overflow:'hidden',textOverflow:'ellipsis'}}>{r.materialName||'—'}</p>
            {r.requiredQty>0&&<p style={{color:C.success,margin:'2px 0 0',fontSize:'11px',fontWeight:'700'}}>{'Потребность: '+fmtMeasure(r.requiredQty,r.requiredUnit)}</p>}
            {r.shortageQty>0&&<p style={{color:C.warning,margin:'2px 0 0',fontSize:'11px',fontWeight:'700'}}>{'Не хватает: '+fmtMeasure(r.shortageQty,r.requiredUnit||r.materialUnit)}</p>}
          </div>
          <div>
            <span style={{color:C.textMuted,fontSize:'10px',textTransform:'uppercase'}}>Смета</span>
            <p style={{color:r.status==='Некорректное количество'?C.danger:C.textSec,margin:'2px 0 0',fontSize:'12px'}}>{r.hasEstimateMaterial?fmtMeasure(r.materialQty,r.materialUnit):'—'}</p>
            <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'10px',lineHeight:1.35}}>{materialNormCoverageComment(r)}</p>
          </div>
          <div style={{display:'flex',gap:'6px',justifyContent:isMobile?'flex-start':'flex-end',flexWrap:'wrap'}}>
            {r.status==='Нет материала в смете'&&canEdit&&<button onClick={()=>addEstimateMaterialFromCoverage(r)} style={btnState(btnGr,false,{padding:'5px 8px',fontSize:'11px'})}><Plus size={11}/>Материал</button>}
            {materialNormCanCreateSupply(r)&&canCreateSupply&&(materialNormSupplyRequestExists(r)?<span style={badge(C.success,C.successLight,C.successBorder)}>Заявка уже есть</span>:<button onClick={()=>createSupplyRequestFromNormCoverage(r)} style={btnState(btnO,false,{padding:'5px 8px',fontSize:'11px'})}><ShoppingCart size={11}/>Заявка</button>)}
            {r.status==='Нет материала в смете'&&canEdit&&<button onClick={()=>markEstimateWorkNoMaterialFromCoverage(r)} style={btnState(btnG,false,{padding:'5px 8px',fontSize:'11px'})}><Check size={11}/>Без материала</button>}
            {r.status==='Нет материала в смете'&&canEdit&&<button onClick={()=>createMaterialNormCoverageTask(r)} style={btnState(btnB,false,{padding:'5px 8px',fontSize:'11px'})}><Bot size={11}/>Поручение</button>}
            {r.rule&&canEdit&&<button onClick={()=>saveMaterialNormOverrideFromCoverage(r)} style={btnState(btnB,false,{padding:'5px 8px',fontSize:'11px'})}>Поправка</button>}
          </div>
        </div>);})}
        {hiddenCoverageRows>0&&<button type="button" onClick={()=>setMobileExpandedRenderLists(prev=>({...prev,[coverageKey]:true}))} style={{...btnB,width:'100%',justifyContent:'center',fontSize:'12px'}}>Показать ещё {hiddenCoverageRows} строк</button>}
        {displayRows.length>0&&<p style={{color:C.textMuted,fontSize:'11px',margin:'2px 0 0'}}>Показано {visibleCoverageRows.length} из {displayRows.length}. Сначала обработайте строки без нормы и материалы без работы.</p>}
      </div>:<p style={{color:C.textMuted,fontSize:'12px',margin:'8px 0 0'}}>Выберите объект с активной сметой заказчика.</p>}
    </div>
  );
}
