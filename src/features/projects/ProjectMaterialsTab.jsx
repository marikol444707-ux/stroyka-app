import React from 'react';
import { createMaterialTransferForm } from '../warehouse/warehouseInitialForms';
import { projectMaterialEstimateDetailsToLoad } from './projectMaterialsUtils';

export default function ProjectMaterialsTab({ ctx, project, projectJournalDiagnostics }) {
  const p = project;
  const {
    API, C, ESTIMATE_PACKAGES, Plus, _normalizeUnit, activeEstimatesForProject, badge,
    brigadeContracts, btnB, btnG, btnGr, btnO, btnR, buildM15Content,
    buildMaterialRequirementContent, card, convertUnits, createBatchSupplyRequestFromMaterialControl,
    estimatePackage, estimateWorkNormRequirementRows, fmtMeasure, history, inp, isLeadership,
    isMobile, materialControlStatus, materialNormControlSummaryForProject,
    loadEstimateDetail, materialReconciliationRows, materialTransfers, materials, renderMaterialAliasControls,
    renderMaterialSupplyAction, setMaterialTransfers, setMaterials, setNewTransfer,
    setShowTransferForm, setWarehouseMain, showPreview, showTransferForm, staff, supplyRequests,
    tbl, tblC, tblH, user, visibleActiveProjects, warehouseMain, workJournal, projects,
    ProjectMaterialsControlPanel, ProjectMaterialsStockPanel, ProjectMaterialsTransferPanel,
    newTransfer,
  } = ctx;
  const currentUser = user || {};
  const isLeadershipUser = typeof isLeadership === 'function' ? isLeadership() : Boolean(isLeadership);
  const [estimateLoadError, setEstimateLoadError] = React.useState('');
  const [estimateLoadRetry, setEstimateLoadRetry] = React.useState(0);
  const loadEstimateDetailRef = React.useRef(loadEstimateDetail);
  loadEstimateDetailRef.current = loadEstimateDetail;
  const estimatesToLoad = projectMaterialEstimateDetailsToLoad({
    project: p,
    activeEstimatesForProject,
  });
  const estimatesToLoadKey = estimatesToLoad.map(estimate => estimate.id).sort().join(',');
  const isEstimatePlanLoading = estimatesToLoad.length > 0 && !estimateLoadError;

  React.useEffect(() => {
    if (!estimatesToLoadKey || typeof loadEstimateDetailRef.current !== 'function') return undefined;
    let active = true;
    setEstimateLoadError('');
    Promise.all(estimatesToLoad.map(estimate => loadEstimateDetailRef.current(estimate)))
      .catch(() => {
        if (active) setEstimateLoadError('Не удалось загрузить материалы активных смет.');
      });
    return () => { active = false; };
    // IDs change after detail rows are merged into estimatesList.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.name, estimatesToLoadKey, estimateLoadRetry]);

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
        <div>
          <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Материалы по смете</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>Плановая потребность активных смет, заявки, поставки и фактический остаток объекта.</p>
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
      {isEstimatePlanLoading && (
        <div role="status" style={{padding:'14px 0',marginBottom:'12px',borderTop:'1px solid '+C.border,borderBottom:'1px solid '+C.border,color:C.textSec,fontSize:'12px'}}>
          Загружаем материалы активных смет объекта...
        </div>
      )}
      {estimateLoadError && (
        <div role="alert" style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',padding:'12px 0',marginBottom:'12px',borderTop:'1px solid '+C.warningBorder,borderBottom:'1px solid '+C.warningBorder}}>
          <span style={{color:C.warning,fontSize:'12px'}}>{estimateLoadError}</span>
          <button type="button" onClick={()=>setEstimateLoadRetry(value=>value+1)} style={{...btnB,padding:'6px 10px',fontSize:'11px'}}>Повторить</button>
        </div>
      )}
      {!isEstimatePlanLoading && !estimateLoadError && <ProjectMaterialsControlPanel
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
          />}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',margin:'20px 0 10px'}}>
        <div>
          <b style={{color:C.text,fontSize:'14px',fontWeight:'700'}}>Фактический склад объекта</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>Только принятые и перемещённые материалы, которые уже числятся на объекте.</p>
        </div>
        {(isLeadershipUser||currentUser.role==='прораб'||currentUser.role==='кладовщик')&&(
          <button onClick={async()=>{
            const res=await fetch(API+'/material-transfers?project_name='+encodeURIComponent(p.name));
            const data=await res.json();
            setMaterialTransfers(Array.isArray(data)?data:[]);
            setNewTransfer(createMaterialTransferForm({ fromLocation: p.name }));
            setShowTransferForm(!showTransferForm);
          }} style={btnO}><Plus size={14}/>Передать материал</button>
        )}
      </div>
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
