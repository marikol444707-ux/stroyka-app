import React from 'react';
import { createMaterialTransferForm } from '../warehouse/warehouseInitialForms';

export default function ProjectMaterialsTab({ ctx, project, projectJournalDiagnostics }) {
  const p = project;
  const {
    API, C, ESTIMATE_PACKAGES, Plus, _normalizeUnit, activeEstimatesForProject, badge,
    brigadeContracts, btnB, btnG, btnGr, btnO, btnR, buildM15Content,
    buildMaterialRequirementContent, card, convertUnits, createBatchSupplyRequestFromMaterialControl,
    estimatePackage, estimateWorkNormRequirementRows, fmtMeasure, history, inp, isLeadership,
    isMobile, materialControlStatus, materialNormControlSummaryForProject,
    materialReconciliationRows, materialTransfers, materials, renderMaterialAliasControls,
    renderMaterialSupplyAction, setMaterialTransfers, setMaterials, setNewTransfer,
    setShowTransferForm, setWarehouseMain, showPreview, showTransferForm, staff, supplyRequests,
    tbl, tblC, tblH, user, visibleActiveProjects, warehouseMain, workJournal, projects,
    ProjectMaterialsControlPanel, ProjectMaterialsStockPanel, ProjectMaterialsTransferPanel,
    newTransfer,
  } = ctx;

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Материалы объекта</b>
            <div style={{display:'flex',gap:'8px'}}>
              {(isLeadership()||user.role==='прораб'||user.role==='кладовщик')&&(
          <button onClick={async()=>{
            const res=await fetch(API+'/material-transfers?project_name='+encodeURIComponent(p.name));
            const data=await res.json();
            setMaterialTransfers(Array.isArray(data)?data:[]);
            setNewTransfer(createMaterialTransferForm({ fromLocation: p.name }));
            setShowTransferForm(!showTransferForm);
          }} style={btnO}><Plus size={14}/>Передать материал</button>)}
        </div>
      </div>
      {(()=>{
        const diag=projectJournalDiagnostics(p.name);
        if(!diag.smetaOutsideRows.length&&!diag.smetaOverRows.length) return null;
        return(<div style={{...card,padding:'12px',marginBottom:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}>
          <b style={{color:C.warning,fontSize:'13px'}}>Сметная сверка требует внимания</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'4px 0 0'}}>Вне сметы: {diag.smetaOutsideRows.length} · нужен алиас/решение: {diag.aliasNeededRows.length} · сверх плана: {diag.smetaOverRows.length}</p>
          <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginTop:'8px'}}>
            {diag.aliasNeededRows.slice(0,6).map((r,idx)=><span key={(r.key||r.name||'a')+'-'+idx} style={badge(C.warning,C.warningLight,C.warningBorder)}>{r.name}</span>)}
          </div>
        </div>);
      })()}
      <ProjectMaterialsControlPanel
        projectName={p.name}
        rows={materialReconciliationRows(p.name)}
        normRows={estimateWorkNormRequirementRows(p.name)}
        normCtrl={materialNormControlSummaryForProject(p.name)}
        buildRowsForPackage={(workPackage)=>materialReconciliationRows(p.name, workPackage)}
        buildNormRowsForPackage={(workPackage)=>estimateWorkNormRequirementRows(p.name, workPackage)}
        buildNormCtrlForPackage={(workPackage)=>materialNormControlSummaryForProject(p.name, workPackage)}
        isMobile={isMobile}
        C={C}
        card={card}
        tbl={tbl}
        tblH={tblH}
        tblC={tblC}
        btnB={btnB}
        badge={badge}
        fmtMeasure={fmtMeasure}
        materialControlStatus={materialControlStatus}
        renderMaterialSupplyAction={renderMaterialSupplyAction}
        renderMaterialAliasControls={renderMaterialAliasControls}
            onCreateSupplyForRows={(rows)=>createBatchSupplyRequestFromMaterialControl(p.name, rows)}
            showPreview={showPreview}
            buildMaterialRequirementContent={buildMaterialRequirementContent}
            onIssueMaterial={(row)=>{
              setNewTransfer(createMaterialTransferForm({
                materialName: row.name || '',
                unit: row.unit || 'шт',
                workPackage: row.packageName || row.workPackage || '',
                fromLocation: p.name,
                notes: 'Выдача мастеру из контроля материалов',
              }));
              setShowTransferForm(true);
            }}
          />
      <ProjectMaterialsStockPanel
        projectName={p.name}
        materials={materials}
        warehouseMain={warehouseMain}
        isMobile={isMobile}
        C={C}
        card={card}
      />

      <ProjectMaterialsTransferPanel
        projectName={p.name}
        showTransferForm={showTransferForm}
        setShowTransferForm={setShowTransferForm}
        newTransfer={newTransfer}
        setNewTransfer={setNewTransfer}
        materialTransfers={materialTransfers}
        setMaterialTransfers={setMaterialTransfers}
        warehouseMain={warehouseMain}
        setWarehouseMain={setWarehouseMain}
        materials={materials}
        setMaterials={setMaterials}
        visibleProjects={visibleActiveProjects(projects)}
        supplyRequests={supplyRequests}
        staff={staff}
        brigadeContracts={brigadeContracts}
        workJournal={workJournal}
        history={history}
        workPackageOptions={[...new Set([...(activeEstimatesForProject(p,'Заказчик')||[]).map(estimatePackage), ...ESTIMATE_PACKAGES].filter(Boolean))]}
        user={user}
        C={C}
        card={card}
        inp={inp}
        tbl={tbl}
        tblH={tblH}
        tblC={tblC}
        btnO={btnO}
        btnG={btnG}
        btnGr={btnGr}
        btnB={btnB}
        btnR={btnR}
        normalizeUnit={_normalizeUnit}
        convertUnits={convertUnits}
        fmtMeasure={fmtMeasure}
        showPreview={showPreview}
        buildM15Content={buildM15Content}
      />
  </div>
  );
}
