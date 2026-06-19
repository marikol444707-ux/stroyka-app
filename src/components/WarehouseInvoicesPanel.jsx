import React from 'react';
import { Plus } from 'lucide-react';
import { WarehouseInvoiceCard, WarehouseInvoiceForm } from './warehouse/WarehouseInvoicesParts';

export default function WarehouseInvoicesPanel({
  showForm,
  setShowForm,
  newInvoice,
  setNewInvoice,
  suppliers,
  projects,
  estimatesList,
  getProjectWorkPackageOptions,
  getProjectEstimateWorkOptions,
  invoices,
  saveInvoiceNew,
  uploadPhoto,
  fileSrc,
  setShowPhotoModal,
  setSverkaModal,
  warehouseInvoiceItems,
  isSupplyDeliveryInvoice,
  warehouseInvoiceEstimateControl,
  renderInvoiceControlActions,
  showPreview,
  buildInvoiceContent,
  setShowQRModal,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnR,
  tbl,
  tblH,
  tblC,
  VAT_OPTIONS,
  UNITS,
  MATERIAL_CATEGORIES,
  isMobile = false,
}) {
  const invoiceItems = newInvoice.items || [];
  const invoiceTotal = invoiceItems.reduce((sum, item) => sum + (Number(item.lineTotal || 0) || Number(item.quantity || 0) * Number(item.price || 0)), 0);
  const materialEstimates = (estimatesList || []).filter(est => est.projectName === newInvoice.location && est.smetaType === 'Материалы');
  const draftEstimateControl = warehouseInvoiceEstimateControl ? warehouseInvoiceEstimateControl(newInvoice) : [];
  const draftControlIssues = draftEstimateControl.filter(row => ['danger', 'warning'].includes(row.severity));

  const controlTone = (row = {}) => {
    if (row.severity === 'danger') return {color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
    if (row.severity === 'warning') return {color:C.warning, bg:C.warningLight, border:C.warningBorder};
    if (row.severity === 'info') return {color:C.info, bg:C.infoLight, border:C.infoBorder};
    if (row.severity === 'success') return {color:C.success, bg:C.successLight, border:C.successBorder};
    return {color:C.textSec, bg:C.bg, border:C.border};
  };

  const invoiceControlSummary = (rows = []) => {
    const filled = rows.filter(row => row.name);
    return {
      ok: filled.filter(row => row.severity === 'success').length,
      outside: filled.filter(row => row.status === 'Вне сметы').length,
      composite: filled.filter(row => row.isCompositeWorkMaterial || row.status === 'Комплектация работы').length,
      over: filled.filter(row => row.overText && row.overText !== '—').length,
      price: filled.filter(row => row.priceOverText && row.priceOverText !== '—').length,
    };
  };

  const renderControlBadge = (row) => {
    const tone = controlTone(row);
    return (
      <span style={{
        display:'inline-flex',
        alignItems:'center',
        gap:'4px',
        padding:'3px 8px',
        borderRadius:'999px',
        backgroundColor:tone.bg,
        border:'1px solid '+tone.border,
        color:tone.color,
        fontSize:'10px',
        fontWeight:'800',
        whiteSpace:'nowrap',
      }}>
        {row?.status || '—'}
      </span>
    );
  };

  const buildEstimateReconciliationReport = (estimate) => {
    const smetaItems = (estimate.sections || []).flatMap(section => section.items || []);
    const filledItems = invoiceItems.filter(item => item.name && item.quantity);
    let report = '📊 СВЕРКА НАКЛАДНОЙ СО СМЕТОЙ\n';
    report += 'Смета: ' + estimate.name + '\n\n';

    const norm = (value) => String(value || '').toLowerCase().replace(/[хx×]/g, 'x').replace(/[,.]/g, '.').replace(/\s+/g, ' ').trim();

    filledItems.forEach(invItem => {
      const matched = smetaItems.find(si => (
        norm(si.name).includes(norm(invItem.name)) ||
        norm(invItem.name).includes(norm(si.name)) ||
        norm(si.name).split(' ').filter(word => word.length > 3).every(word => norm(invItem.name).includes(word))
      ));
      if (matched) {
        const need = Number(matched.quantity || 0);
        const got = Number(invItem.quantity || 0);
        const diff = need - got;
        report += `✅ ${invItem.name}\n`;
        report += `   По смете: ${need} ${matched.unit}\n`;
        report += `   Получено: ${got} ${invItem.unit}\n`;
        report += diff > 0 ? `   ⚠️ Дефицит: ${diff}\n\n` : '   ✅ Достаточно\n\n';
      } else {
        report += `❓ ${invItem.name} — не найдено в смете\n\n`;
      }
    });

    return report;
  };

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Накладные</b>
        <button onClick={() => setShowForm(!showForm)} style={btnO}><Plus size={14}/>Новая накладная</button>
      </div>

      {showForm && (
        <WarehouseInvoiceForm
          newInvoice={newInvoice}
          setNewInvoice={setNewInvoice}
          suppliers={suppliers}
          projects={projects}
          materialEstimates={materialEstimates}
          getProjectWorkPackageOptions={getProjectWorkPackageOptions}
          getProjectEstimateWorkOptions={getProjectEstimateWorkOptions}
          invoiceItems={invoiceItems}
          invoiceTotal={invoiceTotal}
          draftEstimateControl={draftEstimateControl}
          draftControlIssues={draftControlIssues}
          saveInvoiceNew={saveInvoiceNew}
          uploadPhoto={uploadPhoto}
          fileSrc={fileSrc}
          setShowForm={setShowForm}
          setShowPhotoModal={setShowPhotoModal}
          setSverkaModal={setSverkaModal}
          buildEstimateReconciliationReport={buildEstimateReconciliationReport}
          renderControlBadge={renderControlBadge}
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnB={btnB}
          btnR={btnR}
          VAT_OPTIONS={VAT_OPTIONS}
          UNITS={UNITS}
          MATERIAL_CATEGORIES={MATERIAL_CATEGORIES}
          isMobile={isMobile}
        />
      )}

      {(invoices || []).map(inv => {
        const invoiceRows = warehouseInvoiceItems(inv);
        const estimateControl = warehouseInvoiceEstimateControl ? warehouseInvoiceEstimateControl(inv) : [];
        const estimateIssues = estimateControl.filter(row => ['danger', 'warning'].includes(row.severity));
        return (
          <WarehouseInvoiceCard
            key={inv.id}
            inv={inv}
            invoiceRows={invoiceRows}
            estimateControl={estimateControl}
            estimateIssues={estimateIssues}
            isSupplyDeliveryInvoice={isSupplyDeliveryInvoice}
            invoiceControlSummary={invoiceControlSummary}
            renderControlBadge={renderControlBadge}
            renderInvoiceControlActions={renderInvoiceControlActions}
            showPreview={showPreview}
            buildInvoiceContent={buildInvoiceContent}
            setShowQRModal={setShowQRModal}
            fileSrc={fileSrc}
            setShowPhotoModal={setShowPhotoModal}
            C={C}
            card={card}
            btnB={btnB}
            btnG={btnG}
            tbl={tbl}
            tblH={tblH}
            tblC={tblC}
            isMobile={isMobile}
          />
        );
      })}

      {(invoices || []).length === 0 && <p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Накладных нет</p>}
    </div>
  );
}
