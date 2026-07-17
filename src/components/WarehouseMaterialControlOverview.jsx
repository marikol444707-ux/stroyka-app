import React from 'react';
import { Download, Eye, Printer } from 'lucide-react';
import AllProjectsMaterialProjectionReview from './AllProjectsMaterialProjectionReview';

export default function WarehouseMaterialControlOverview({
  C,
  badge,
  btnB,
  btnG,
  buildMaterialRequirementContent,
  card,
  exportToExcel,
  isFinanceRole,
  isMobile,
  isLeadership,
  canReviewSupplyRequests = true,
  materialControlSummaryForProject,
  materialReconciliationRows,
  parseSupplyItems,
  projects,
  setSelectedWarehouseProject,
  setWarehouseTab,
  showPreview,
  supplyRequests,
  visibleActiveProjects,
}) {
  const isFinanceUser = typeof isFinanceRole === 'function' ? isFinanceRole() : Boolean(isFinanceRole);
  const isLeadershipUser = typeof isLeadership === 'function' ? isLeadership() : Boolean(isLeadership);
  const activeProjects = visibleActiveProjects(projects);

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',gap:'10px',flexWrap:'wrap'}}>
        <div>
          <h3 style={{color:C.text,margin:'0 0 4px',fontSize:'15px',fontWeight:'700'}}>Контроль материалов по сметам</h3>
          <p style={{color:C.textSec,margin:0,fontSize:'12px'}}>Один экран: план из активных смет, заявки, поставки, перемещения, выдача мастерам и списание по работам.</p>
        </div>
        <button onClick={()=>exportToExcel(activeProjects.flatMap(p=>materialReconciliationRows(p.name).map(r=>({Объект:p.name,Материал:r.name,Ед:r.unit,'План по смете':r.planQty,'Норма по работам':r.normPlanQty,'Контрольная потребность':r.controlPlanQty,'Норма выше сметы':r.normOverEstimateQty,'Расход сверх контроля':r.usedOverControlQty,'Строк сметы':r.planSourceCount||(r.planDetails||[]).length,'Строк норм':r.normSourceCount||(r.normDetails||[]).length,Разделы:(r.sections||[]).join('; '),'Работы-основания':(r.workRefs||[]).join('; '),Заявки:r.requested,'В пути':r.inTransit,Накладные:r.invoiceReceived,Поставки:r.supplyReceived,Перемещено:r.movedNet,'Всего получено':r.supplied,Выдано:r.issued,Списано:r.used,'У мастеров':r.masterBalance,Остаток:r.stock,'Расчётный остаток':r.expectedStock,'Расхождение склада':r.stockDiff,Докупить:r.toBuy,Статус:r.stockMismatch?'Расхождение склада':r.issued>0&&r.usedWithoutIssue>0?'Списано сверх выдачи':r.usedOverControlQty>0?'Расход сверх нормы':r.isOutsideEstimate?'Вне сметы':r.normOverEstimateQty>0?'Норма выше сметы':r.toBuy>0?'Докупить':r.shortage>0?'Закрывается':r.masterBalance>0?'У мастеров':r.over>0?'Сверх контроля':'Закрыто'}))),'Контроль_материалов')} style={btnG}><Download size={14}/>Excel</button>
      </div>
      <AllProjectsMaterialProjectionReview
        projects={activeProjects}
        projectIdentityCandidates={projects}
        materialReconciliationRows={materialReconciliationRows}
        supplyRequests={supplyRequests}
        parseSupplyItems={parseSupplyItems}
        C={C}
        isMobile={isMobile}
        canReviewSupplyRequests={canReviewSupplyRequests}
      />
      {activeProjects.map(p=>{const s=materialControlSummaryForProject(p.name);const hasIssue=s.toBuyRows.length||s.outsideRows.length||s.mismatchRows.length||s.stockMismatchRows.length;return(<div key={p.id||p.name} style={{...card,padding:'14px',marginBottom:'10px',borderLeft:'4px solid '+(s.stockMismatchRows.length?C.danger:s.toBuyRows.length?C.warning:s.outsideRows.length?C.danger:hasIssue?C.info:C.success)}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
          <div style={{flex:1,minWidth:'240px'}}>
            <b style={{color:C.text,fontSize:'14px'}}>{p.name}</b>
            <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginTop:'6px'}}>
              <span style={badge(C.textSec,C.bgGray,C.border)}>{'План: '+s.planRows.length}</span>
              <span style={badge(C.success,C.successLight,C.successBorder)}>{'Поставлялось: '+s.suppliedRows.length}</span>
              {s.invoiceRows.length>0&&<span style={badge(C.info,C.infoLight,C.infoBorder)}>{'Накладные: '+s.invoiceRows.length}</span>}
              {s.deliveryRows.length>0&&<span style={badge(C.success,C.successLight,C.successBorder)}>{'Поставки: '+s.deliveryRows.length}</span>}
              {s.movedRows.length>0&&<span style={badge(C.info,C.infoLight,C.infoBorder)}>{'Перемещ.: '+s.movedRows.length}</span>}
              {s.masterBalanceRows.length>0&&<span style={badge(C.info,C.infoLight,C.infoBorder)}>{'У мастеров: '+s.masterBalanceRows.length}</span>}
              <span style={badge(s.toBuyRows.length?C.warning:C.success,s.toBuyRows.length?C.warningLight:C.successLight,s.toBuyRows.length?C.warningBorder:C.successBorder)}>{'Докупить: '+s.toBuyRows.length}</span>
              {s.normOverEstimateRows?.length>0&&<span style={badge(C.warning,C.warningLight,C.warningBorder)}>{'Норма выше сметы: '+s.normOverEstimateRows.length}</span>}
              {s.usedOverControlRows?.length>0&&<span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>{'Расход сверх: '+s.usedOverControlRows.length}</span>}
              {s.outsideRows.length>0&&<span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>{'Вне сметы: '+s.outsideRows.length}</span>}
              {s.mismatchRows.length>0&&<span style={badge(C.warning,C.warningLight,C.warningBorder)}>{'Ед. изм.: '+s.mismatchRows.length}</span>}
              {s.stockMismatchRows.length>0&&<span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>{'Расхождения: '+s.stockMismatchRows.length}</span>}
            </div>
            {(isFinanceUser||isLeadershipUser)&&<p style={{color:C.textMuted,margin:'6px 0 0',fontSize:'11px'}}>План материалов: {Math.round(s.planSum).toLocaleString('ru-RU')+' ₽'} · Оприходовано: {Math.round(s.suppliedSum).toLocaleString('ru-RU')+' ₽'}</p>}
          </div>
          <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
            <button onClick={()=>{setSelectedWarehouseProject(p.name);setWarehouseTab('objects');}} style={{...btnB,padding:'6px 10px',fontSize:'12px'}}><Eye size={13}/>Открыть</button>
            <button onClick={()=>showPreview(buildMaterialRequirementContent(p.name),'Потребность материалов — '+p.name)} style={{...btnG,padding:'6px 10px',fontSize:'12px'}}><Printer size={13}/>Печать</button>
          </div>
        </div>
      </div>);})}
      {activeProjects.length===0&&<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Объектов нет</div>}
    </div>
  );
}
