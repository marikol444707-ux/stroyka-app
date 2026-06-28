import React from 'react';
import { Plus, Search } from 'lucide-react';
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
  materials = [],
  materialControlSummaryForProject,
  setWarehouseTab,
  setSelectedWarehouseProject,
  setNewTransfer,
  setShowTransferForm,
  materialTransfers = [],
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
  const [invoiceSearch, setInvoiceSearch] = React.useState('');
  const invoiceItems = newInvoice.items || [];
  const invoiceTotal = invoiceItems.reduce((sum, item) => sum + (Number(item.lineTotal || 0) || Number(item.quantity || 0) * Number(item.price || 0)), 0);
  const materialEstimates = (estimatesList || []).filter(est => est.projectName === newInvoice.location && est.smetaType === 'Материалы');
  const draftEstimateControl = warehouseInvoiceEstimateControl ? warehouseInvoiceEstimateControl(newInvoice) : [];
  const draftControlIssues = draftEstimateControl.filter(row => ['danger', 'warning'].includes(row.severity));
  const canPrepareTransfer = typeof setNewTransfer === 'function' && typeof setShowTransferForm === 'function';

  const toNum = value => {
    const parsed = Number(String(value ?? '').replace(',', '.').replace(/\s+/g, ''));
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const normalizeText = value => String(value || '')
    .toLowerCase()
    .replace(/[.,;:()«»"']/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const invoiceProjectName = (inv = {}) => (
    inv.location === 'Основной склад' ? '' : (inv.project || inv.location || '')
  );

  const packageOf = (row = {}) => String(row.workPackage || row.work_package || row.packageName || '').trim();
  const invoiceLineKeyFor = ({ materialName = '', workPackage = '', unit = '' } = {}) => [
    normalizeText(materialName),
    normalizeText(workPackage),
    normalizeText(unit),
  ].join('|');

  const stockForInvoiceItem = (projectName, item = {}, ctrl = {}) => {
    if (!projectName) return null;
    const itemPackage = packageOf(ctrl) || packageOf(item);
    const names = [item.name, ctrl.canonicalName, ctrl.name].map(normalizeText).filter(Boolean);
    const projectMaterials = (materials || []).filter(material => material.project === projectName);
    const packageMatches = material => !itemPackage || packageOf(material) === itemPackage;
    const nameMatches = material => {
      const materialName = normalizeText(material.name);
      return names.some(name => materialName === name || (name && (materialName.includes(name) || name.includes(materialName))));
    };
    return projectMaterials.find(material => packageMatches(material) && nameMatches(material)) ||
      projectMaterials.find(nameMatches) ||
      null;
  };

  const transferQuantity = (invoiceQty, stockQty) => {
    const qty = stockQty > 0 ? Math.min(invoiceQty || stockQty, stockQty) : 0;
    if (qty <= 0) return '';
    return String(Math.round(qty * 1000) / 1000);
  };

  const prepareTransferFromInvoice = (inv, invoiceRows, estimateControl) => {
    const projectName = invoiceProjectName(inv);
    if (!projectName) {
      window.alert('Эта накладная заведена на основной склад. Для передачи выберите объектную накладную или сделайте перемещение на объект.');
      return;
    }
    const grouped = new Map();
    (invoiceRows.items || []).forEach((item, index) => {
      if (!item?.name) return;
      const ctrl = estimateControl[index] || {};
      const stock = stockForInvoiceItem(projectName, item, ctrl);
      const materialName = stock?.name || item.name;
      const unit = stock?.unit || ctrl.rowUnit || item.unit || 'шт';
      const workPackage = packageOf(stock || {}) || packageOf(ctrl) || packageOf(item);
      const stockQty = toNum(stock?.quantity);
      const suggestedQty = transferQuantity(toNum(item.quantity), stockQty);
      const key = [materialName, workPackage, unit].join('|||');
      const invoiceLineKey = invoiceLineKeyFor({ materialName: item.name, workPackage, unit });
      const existing = grouped.get(key);
      if (existing) {
        const nextQty = toNum(existing.quantity) + toNum(suggestedQty);
        existing.quantity = stockQty > 0 ? transferQuantity(nextQty, stockQty) : existing.quantity;
        return;
      }
      grouped.set(key, {
        materialName,
        quantity: suggestedQty,
        unit,
        workPackage,
        invoiceId: inv.id || null,
        invoiceLineKey,
        invoiceLineIndex: index,
        invoiceNumber: inv.number || '',
      });
    });

    const transferItems = Array.from(grouped.values()).filter(item => item.materialName);
    if (!transferItems.length) {
      window.alert('В накладной нет строк материалов для передачи.');
      return;
    }
    const first = transferItems[0];
    const invoiceLabel = ['накладной №' + (inv.number || inv.id || ''), inv.date ? 'от ' + inv.date : ''].filter(Boolean).join(' ');
    setSelectedWarehouseProject?.(projectName);
    setNewTransfer({
      materialName: first.materialName,
      quantity: first.quantity,
      unit: first.unit || 'шт',
      workPackage: transferItems.length === 1 ? (first.workPackage || '') : '',
      items: transferItems,
      toPerson: '',
      toPersonRole: '',
      toUserId: '',
      fromLocation: projectName,
      invoiceId: inv.id || null,
      invoiceLineKey: first.invoiceLineKey || '',
      invoiceLineIndex: first.invoiceLineIndex ?? null,
      invoiceNumber: inv.number || '',
      notes: 'Подготовлено из ' + invoiceLabel + '. Проверьте количество перед передачей.',
      transferDate: new Date().toISOString().split('T')[0],
    });
    setWarehouseTab?.('objects');
    setShowTransferForm(true);
  };

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

  const preparedInvoices = (invoices || []).map(inv => {
    const invoiceRows = warehouseInvoiceItems(inv);
    const estimateControl = warehouseInvoiceEstimateControl ? warehouseInvoiceEstimateControl(inv) : [];
    const estimateIssues = estimateControl.filter(row => ['danger', 'warning'].includes(row.severity));
    const projectName = invoiceProjectName(inv);
    const materialSummary = projectName && typeof materialControlSummaryForProject === 'function'
      ? materialControlSummaryForProject(projectName)
      : null;
    return { inv, invoiceRows, estimateControl, estimateIssues, projectName, materialSummary };
  });

  const normalizedInvoiceSearch = normalizeText(invoiceSearch);
  const filteredInvoices = normalizedInvoiceSearch
    ? preparedInvoices.filter(row => {
      const itemText = (row.invoiceRows.items || []).map(item => item.name).join(' ');
      return normalizeText([
        row.inv.number,
        row.inv.date,
        row.inv.supplierName,
        row.inv.acceptedBy,
        row.inv.location,
        row.inv.project,
        row.inv.status,
        itemText,
      ].join(' ')).includes(normalizedInvoiceSearch);
    })
    : preparedInvoices;
  const totalPositions = preparedInvoices.reduce((sum, row) => sum + (row.invoiceRows.items || []).length, 0);
  const filteredPositions = filteredInvoices.reduce((sum, row) => sum + (row.invoiceRows.items || []).length, 0);

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

      <div style={{display:'grid',gridTemplateColumns:isMobile?'repeat(2,minmax(0,1fr))':'repeat(4,minmax(0,1fr))',gap:'8px',marginBottom:'12px'}}>
        <div style={{padding:'10px',border:'1px solid '+C.border,borderRadius:'10px',backgroundColor:C.bg}}>
          <p style={{margin:'0 0 3px',fontSize:'10px',color:C.textSec}}>Накладных</p>
          <b style={{color:C.text,fontSize:'15px'}}>{filteredInvoices.length}</b>
        </div>
        <div style={{padding:'10px',border:'1px solid '+C.border,borderRadius:'10px',backgroundColor:C.bg}}>
          <p style={{margin:'0 0 3px',fontSize:'10px',color:C.textSec}}>Позиций</p>
          <b style={{color:C.text,fontSize:'15px'}}>{filteredPositions}</b>
        </div>
        <div style={{padding:'10px',border:'1px solid '+C.border,borderRadius:'10px',backgroundColor:C.bg}}>
          <p style={{margin:'0 0 3px',fontSize:'10px',color:C.textSec}}>Всего накладных</p>
          <b style={{color:C.text,fontSize:'15px'}}>{preparedInvoices.length}</b>
        </div>
        <div style={{padding:'10px',border:'1px solid '+C.border,borderRadius:'10px',backgroundColor:C.bg}}>
          <p style={{margin:'0 0 3px',fontSize:'10px',color:C.textSec}}>Всего позиций</p>
          <b style={{color:C.text,fontSize:'15px'}}>{totalPositions}</b>
        </div>
      </div>

      <div style={{position:'relative',marginBottom:'12px'}}>
        <Search size={14} style={{position:'absolute',left:12,top:'50%',transform:'translateY(-50%)',color:C.textMuted}} />
        <input
          value={invoiceSearch}
          onChange={event => setInvoiceSearch(event.target.value)}
          placeholder="Поиск: номер, объект, поставщик, материал"
          style={{...inp,marginBottom:0,paddingLeft:34,width:'100%',boxSizing:'border-box'}}
        />
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

      {filteredInvoices.map(({ inv, invoiceRows, estimateControl, estimateIssues, projectName, materialSummary }) => {
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
            projectName={projectName}
            materialSummary={materialSummary}
            materialTransfers={materialTransfers}
            onPrepareTransfer={canPrepareTransfer ? () => prepareTransferFromInvoice(inv, invoiceRows, estimateControl) : null}
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
      {(invoices || []).length > 0 && filteredInvoices.length === 0 && <p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Поиск ничего не нашёл</p>}
    </div>
  );
}
