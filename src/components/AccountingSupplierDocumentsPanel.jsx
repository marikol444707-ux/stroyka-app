import React from 'react';
import { AlertTriangle, ChevronDown, ChevronUp, Eye, FileText, Link2, RefreshCw, Search } from 'lucide-react';
import { API } from '../api';
import { buildAccountingInvoiceRows } from '../utils/accountingInvoices';
import {
  groupSuppliers,
  normalizeSupplierNameKey,
  sourceMeta,
  supplierMatchesRecord,
  supplierSourceInfo,
} from '../utils/supplierUtils';

const money = value => Math.round(Number(value || 0)).toLocaleString('ru-RU') + ' ₽';

const normalizeKey = value => String(value || '')
  .toLowerCase()
  .replace(/["'«»„“”]/g, '')
  .replace(/\b(ооо|оао|ао|ип|зао|пао|общество|с ограниченной|ответственностью)\b/g, ' ')
  .replace(/[^а-яa-z0-9]+/gi, ' ')
  .replace(/\s+/g, ' ')
  .trim();

export default function AccountingSupplierDocumentsPanel({
  C,
  card,
  btnG,
  btnB,
  inp,
  invoices = [],
  supplierInvoices = [],
  suppliers = [],
  warehouseInvoiceEstimateControl,
  fileSrc,
  setShowPhotoModal,
  refreshData,
  matchSearch,
  listSearch,
  setListSearch,
}) {
  const [openedSupplier, setOpenedSupplier] = React.useState('');
  const [openedDoc, setOpenedDoc] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [backfillPreview, setBackfillPreview] = React.useState(null);
  const [bulkBackfillPreview, setBulkBackfillPreview] = React.useState(null);

  const rows = React.useMemo(
    () => buildAccountingInvoiceRows(invoices, warehouseInvoiceEstimateControl, { includeControls: false }),
    [invoices, warehouseInvoiceEstimateControl]
  );

  const supplierInvoiceById = React.useMemo(() => {
    const map = new Map();
    (supplierInvoices || []).forEach(invoice => map.set(String(invoice.id), invoice));
    return map;
  }, [supplierInvoices]);

  const supplierById = React.useMemo(() => {
    const map = new Map();
    (suppliers || []).forEach(supplier => map.set(String(supplier.id), supplier));
    return map;
  }, [suppliers]);

  const supplierGroups = React.useMemo(() => groupSuppliers(suppliers), [suppliers]);

  const groups = React.useMemo(() => {
    const map = new Map();
    const supplierGroupById = new Map();
    supplierGroups.forEach(group => {
      (group._supplierIds || [group.id]).forEach(id => {
        if (id) supplierGroupById.set(String(id), group);
      });
    });
    const findSupplierGroup = ({ supplierId, supplierName, record }) => {
      if (supplierId && supplierGroupById.has(String(supplierId))) return supplierGroupById.get(String(supplierId));
      const matchRecord = record || { supplierId, supplierName };
      return supplierGroups.find(group => supplierMatchesRecord(group, matchRecord));
    };
    const ensureGroup = ({ supplierId, supplierName, record }) => {
      const supplierGroup = findSupplierGroup({ supplierId, supplierName, record });
      const supplier = supplierGroup || (supplierId ? supplierById.get(String(supplierId)) : null);
      const name = supplier?.name || supplierName || 'Поставщик не указан';
      const key = supplierGroup
        ? `group:${supplierGroup.id}`
        : supplierId
          ? `id:${supplierId}`
          : `name:${normalizeSupplierNameKey(name) || normalizeKey(name) || 'unknown'}`;
      if (!map.has(key)) {
        map.set(key, {
          key,
          supplierId: supplierId || supplier?.id || null,
          supplierName: name,
          supplier,
          supplierIds: supplier?._supplierIds || (supplier?.id ? [supplier.id] : []),
          duplicateCount: supplier?._duplicateCount || 1,
          sourceInfo: supplierSourceInfo(supplier || {}, {}),
          docs: [],
          amount: 0,
          paid: 0,
          unlinked: 0,
          noPhotos: 0,
          mismatches: 0,
        });
      }
      return map.get(key);
    };

    rows.forEach(row => {
      const invoice = row.invoice || {};
      const directSupplierInvoice = invoice.supplierInvoiceId
        ? supplierInvoiceById.get(String(invoice.supplierInvoiceId))
        : null;
      const linkedSupplierInvoice = directSupplierInvoice || (supplierInvoices || []).find(supplierInvoice => (
        String(supplierInvoice.warehouseInvoiceId || supplierInvoice.warehouse_invoice_id || '') === String(invoice.id)
      ));
      const supplierId = invoice.supplierId || invoice.supplier_id || linkedSupplierInvoice?.supplierId || linkedSupplierInvoice?.supplier_id;
      const supplierName = invoice.supplierName || invoice.supplier_name || linkedSupplierInvoice?.supplierName;
      const group = ensureGroup({ supplierId, supplierName, record: {
        supplierId,
        supplierName,
        supplier: supplierName,
      } });
      const supplierAmount = Number(linkedSupplierInvoice?.amount || linkedSupplierInvoice?.totalAmount || 0);
      const amountMismatch = supplierAmount > 0 && row.amount > 0 && Math.abs(supplierAmount - row.amount) > Math.max(1, row.amount * 0.05);
      const doc = {
        type: 'warehouse',
        id: `warehouse:${invoice.id}`,
        warehouseInvoice: invoice,
        supplierInvoice: linkedSupplierInvoice,
        number: invoice.number || invoice.id,
        date: invoice.date || '',
        projectName: invoice.project || invoice.location || '',
        amount: row.amount,
        paidAmount: row.paidAmount,
        status: row.status,
        photos: row.photos,
        items: invoice.items || [],
        issueRows: row.issueRows,
        linked: Boolean(linkedSupplierInvoice),
        amountMismatch,
      };
      group.docs.push(doc);
      group.amount += row.amount;
      group.paid += row.paidAmount;
      if (!doc.linked) group.unlinked += 1;
      if (!doc.photos.length) group.noPhotos += 1;
      if (amountMismatch) group.mismatches += 1;
    });

    (supplierInvoices || []).forEach(invoice => {
      const alreadyLinked = invoice.warehouseInvoiceId || invoice.warehouse_invoice_id;
      if (alreadyLinked) return;
      const group = ensureGroup({ supplierId: invoice.supplierId || invoice.supplier_id, supplierName: invoice.supplierName, record: invoice });
      const amount = Number(invoice.amount || invoice.totalAmount || 0);
      group.docs.push({
        type: 'supplier',
        id: `supplier:${invoice.id}`,
        supplierInvoice: invoice,
        number: invoice.invoiceNumber || invoice.id,
        date: invoice.invoiceDate || '',
        projectName: invoice.projectName || '',
        amount,
        paidAmount: Number(invoice.paidAmount || 0),
        status: invoice.status || 'На утверждении',
        photos: [invoice.fileUrl, invoice.photoUrl].filter(Boolean),
        items: [],
        issueRows: [],
        linked: false,
        amountMismatch: false,
      });
      group.amount += amount;
      group.paid += Number(invoice.paidAmount || 0);
      group.unlinked += 1;
      if (!invoice.fileUrl && !invoice.photoUrl) group.noPhotos += 1;
    });

    return Array.from(map.values())
      .map(group => ({
        ...group,
        sourceInfo: supplierSourceInfo(group.supplier || {}, {
          warehouseInvoices: group.docs.filter(doc => doc.type === 'warehouse').map(doc => doc.warehouseInvoice).filter(Boolean),
        }),
      }))
      .filter(group => !listSearch || (typeof matchSearch === 'function'
        ? matchSearch(listSearch, group.supplierName, ...group.docs.map(doc => `${doc.number} ${doc.projectName}`))
        : normalizeKey(group.supplierName).includes(normalizeKey(listSearch))))
      .sort((a, b) => b.amount - a.amount || a.supplierName.localeCompare(b.supplierName, 'ru'));
  }, [rows, supplierInvoices, supplierById, supplierGroups, supplierInvoiceById, listSearch, matchSearch]);

  const totals = React.useMemo(() => groups.reduce((acc, group) => {
    acc.suppliers += 1;
    acc.docs += group.docs.length;
    acc.amount += group.amount;
    acc.unlinked += group.unlinked;
    acc.noPhotos += group.noPhotos;
    acc.mismatches += group.mismatches;
    return acc;
  }, { suppliers: 0, docs: 0, amount: 0, unlinked: 0, noPhotos: 0, mismatches: 0 }), [groups]);

  const runBackfill = async () => {
    setBusy(true);
    try {
      const res = await fetch(API + '/supplier-documents/backfill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 200 }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.detail || data.error) {
        alert('Предпросмотр сверки не выполнен: ' + (data.detail || data.error || res.status));
        return;
      }
      setBulkBackfillPreview({
        items: data.items || [],
        checked: data.checked || 0,
        linked: data.linked || 0,
        createdAt: new Date().toISOString(),
      });
    } finally {
      setBusy(false);
    }
  };

  const applyBulkBackfillPreview = async event => {
    event?.stopPropagation?.();
    const warehouseInvoiceIds = (bulkBackfillPreview?.items || [])
      .map(item => Number(item.warehouseInvoiceId))
      .filter(Boolean);
    if (!warehouseInvoiceIds.length) {
      alert('Нет накладных для применения сверки');
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(API + '/supplier-documents/backfill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ apply: true, warehouseInvoiceIds, limit: warehouseInvoiceIds.length }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.detail || data.error || (data.errors || []).length) {
        const firstError = (data.errors || [])[0] || {};
        alert('Сверка не выполнена: ' + (data.detail || data.error || firstError.error || res.status));
        return;
      }
      const reviewCount = (data.items || []).filter(item => item.needsReview).length;
      setBulkBackfillPreview(null);
      alert('Сверка завершена. Связано: ' + (data.linked || 0) + '. Проверено: ' + (data.checked || 0) + (reviewCount ? '. Нужно уточнить: ' + reviewCount : ''));
      if (typeof refreshData === 'function') await refreshData();
    } finally {
      setBusy(false);
    }
  };

  const runBackfillForDoc = async (doc, event) => {
    event?.stopPropagation?.();
    const warehouseInvoiceId = doc?.warehouseInvoice?.id;
    if (!warehouseInvoiceId) {
      alert('Не найден ID складской накладной для точечной сверки');
      return;
    }
    setBusy(true);
    try {
      const previewRes = await fetch(API + '/supplier-documents/backfill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ warehouseInvoiceId, limit: 1 }),
      });
      const preview = await previewRes.json().catch(() => ({}));
      if (!previewRes.ok || preview.detail || preview.error) {
        alert('Предпросмотр сверки не выполнен: ' + (preview.detail || preview.error || previewRes.status));
        return;
      }
      setBackfillPreview({
        docId: doc.id,
        warehouseInvoiceId,
        item: (preview.items || [])[0] || {},
        fallbackNumber: doc.number,
        fallbackAmount: doc.amount,
      });
    } finally {
      setBusy(false);
    }
  };

  const applyBackfillPreview = async (preview, event) => {
    event?.stopPropagation?.();
    const warehouseInvoiceId = preview?.warehouseInvoiceId;
    if (!warehouseInvoiceId) {
      alert('Не найден ID складской накладной для сверки');
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(API + '/supplier-documents/backfill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ apply: true, warehouseInvoiceId, limit: 1 }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.detail || data.error || (data.errors || []).length) {
        const firstError = (data.errors || [])[0] || {};
        alert('Сверка не выполнена: ' + (data.detail || data.error || firstError.error || res.status));
        return;
      }
      const resultItem = (data.items || [])[0] || {};
      setBackfillPreview(null);
      alert('Первичка связана. ' + (resultItem.needsReview ? 'Документ оставлен на ручную проверку: ' + (resultItem.reviewReason || '') : 'Документ готов к сверке.'));
      if (typeof refreshData === 'function') await refreshData();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'14px'}}>
        <div>
          <b style={{color:C.text,fontSize:'16px'}}>Документы от поставщиков</b>
          <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Сверка счетов, УПД, складских накладных, фото и оплат по каждому поставщику.</p>
        </div>
        <button disabled={busy} onClick={runBackfill} style={{...btnG,opacity:busy?0.6:1}}>
          <RefreshCw size={14}/>Предпросмотр старых
        </button>
      </div>

      {bulkBackfillPreview && (
        <div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:C.warningLight,border:'1px solid '+C.warningBorder}}>
          {(() => {
            const items = bulkBackfillPreview.items || [];
            const reviewItems = items.filter(item => item.needsReview);
            const readyItems = items.filter(item => !item.needsReview);
            return (
              <>
                <div style={{display:'flex',justifyContent:'space-between',gap:'10px',alignItems:'flex-start',flexWrap:'wrap'}}>
                  <div>
                    <b style={{color:C.text,fontSize:'14px'}}>Предпросмотр массовой сверки</b>
                    <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>
                      Найдено {items.length} накладных: готово {readyItems.length}, нужно уточнить {reviewItems.length}. Склад и оплаты повторно не создаются.
                    </p>
                  </div>
                  <div style={{display:'flex',gap:'8px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                    <button disabled={busy || !items.length} onClick={applyBulkBackfillPreview} style={{...btnG,padding:'7px 10px',fontSize:'12px',opacity:(busy || !items.length)?0.6:1}}>
                      Применить показанные
                    </button>
                    <button disabled={busy} onClick={()=>setBulkBackfillPreview(null)} style={{...btnB,padding:'7px 10px',fontSize:'12px',opacity:busy?0.6:1}}>
                      Отмена
                    </button>
                  </div>
                </div>
                {items.length ? (
                  <div style={{marginTop:'10px',display:'grid',gap:'6px',maxHeight:'360px',overflowY:'auto',paddingRight:'4px'}}>
                    {items.map(item => (
                      <div key={item.warehouseInvoiceId} style={{display:'grid',gridTemplateColumns:'minmax(120px,1fr) minmax(120px,1fr) minmax(110px,auto)',gap:'8px',alignItems:'center',padding:'8px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}>
                        <span style={{color:C.text,fontSize:'12px',fontWeight:700}}>№ {item.number || item.warehouseInvoiceId}</span>
                        <span style={{color:C.textSec,fontSize:'12px'}}>{item.supplierName || 'Поставщик не указан'} · {item.projectName || 'без объекта'} · {money(item.amount)}</span>
                        <span style={{color:item.needsReview?C.warning:C.success,fontSize:'11px',fontWeight:800,textAlign:'right'}}>
                          {item.needsReview ? 'Нужно уточнить' : 'Готово'}
                        </span>
                        {item.needsReview && (
                          <span style={{gridColumn:'1 / -1',color:C.warning,fontSize:'11px'}}>
                            {item.reviewReason || 'проверьте поставщика/документ'}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{color:C.textMuted,fontSize:'12px',margin:'10px 0 0'}}>Несвязанных старых накладных для сверки не найдено.</p>
                )}
              </>
            );
          })()}
        </div>
      )}

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:'10px',marginBottom:'14px'}}>
        <div style={{...card,padding:'12px'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Поставщики</p><b style={{color:C.text,fontSize:'18px'}}>{totals.suppliers}</b></div>
        <div style={{...card,padding:'12px'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Документы</p><b style={{color:C.text,fontSize:'18px'}}>{totals.docs}</b></div>
        <div style={{...card,padding:'12px',backgroundColor:C.accentLight}}><p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px'}}>Сумма</p><b style={{color:C.accent,fontSize:'18px'}}>{money(totals.amount)}</b></div>
        <div style={{...card,padding:'12px',backgroundColor:totals.unlinked?C.warningLight:C.successLight}}><p style={{color:totals.unlinked?C.warning:C.success,fontSize:'11px',margin:'0 0 4px'}}>Не связано</p><b style={{color:totals.unlinked?C.warning:C.success,fontSize:'18px'}}>{totals.unlinked}</b></div>
      </div>

      <div style={{position:'relative',marginBottom:'12px'}}>
        <Search size={15} style={{position:'absolute',left:'12px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
        <input value={listSearch || ''} onChange={e=>setListSearch(e.target.value)} placeholder='Поиск по поставщику, номеру накладной или объекту' style={{...inp,marginBottom:0,paddingLeft:'36px'}}/>
      </div>

      {groups.length === 0 ? (
        <div style={{...card,padding:'28px',textAlign:'center',color:C.textMuted}}>Документы поставщиков не найдены</div>
      ) : groups.map(group => {
        const isOpen = openedSupplier === group.key;
        const debt = Math.max(0, group.amount - group.paid);
        const primarySourceMeta = sourceMeta(group.sourceInfo?.primary);
        return (
          <div key={group.key} style={{...card,marginBottom:'10px',overflow:'hidden'}}>
            <button onClick={()=>setOpenedSupplier(isOpen ? '' : group.key)} style={{width:'100%',border:'none',background:'transparent',padding:'14px',display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',cursor:'pointer',textAlign:'left'}}>
              <div>
                <div style={{display:'flex',gap:'8px',alignItems:'center',flexWrap:'wrap'}}>
                  <b style={{color:C.text,fontSize:'14px'}}>{group.supplierName}</b>
                  <span title={group.sourceInfo?.detail || ''} style={{fontSize:'11px',fontWeight:800,color:primarySourceMeta.color,padding:'2px 7px',borderRadius:'999px',background:C.bg,border:'1px solid '+primarySourceMeta.color}}>
                    {primarySourceMeta.label}
                  </span>
                  {group.duplicateCount > 1 && (
                    <span title={'Связанные карточки: ' + (group.supplierIds || []).join(', ')} style={{fontSize:'11px',fontWeight:800,color:C.warning,padding:'2px 7px',borderRadius:'999px',background:C.warningLight,border:'1px solid '+C.warningBorder}}>
                      дублей: {group.duplicateCount}
                    </span>
                  )}
                </div>
                <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0 0'}}>
                  {group.docs.length} док. · {money(group.amount)}{group.paid ? ' · оплачено ' + money(group.paid) : ''}{debt ? ' · долг ' + money(debt) : ''}
                </p>
                {isOpen && group.supplierIds?.length > 1 && (
                  <p style={{color:C.textMuted,fontSize:'11px',margin:'3px 0 0'}}>Связанные ID: {group.supplierIds.join(', ')}</p>
                )}
              </div>
              <div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap',justifyContent:'flex-end'}}>
                {group.unlinked > 0 && <span style={{color:C.warning,fontSize:'11px',fontWeight:800}}>не связано {group.unlinked}</span>}
                {group.noPhotos > 0 && <span style={{color:C.danger,fontSize:'11px',fontWeight:800}}>без фото {group.noPhotos}</span>}
                {group.mismatches > 0 && <span style={{color:C.danger,fontSize:'11px',fontWeight:800}}>расхождения {group.mismatches}</span>}
                {isOpen ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
              </div>
            </button>
            {isOpen && (
              <div style={{borderTop:'1px solid '+C.border}}>
                {group.docs.sort((a, b) => String(b.date || '').localeCompare(String(a.date || ''))).map(doc => {
                  const docOpen = openedDoc === doc.id;
                  const linkedInvoice = doc.supplierInvoice;
                  const supplierAmount = Number(linkedInvoice?.amount || linkedInvoice?.totalAmount || 0);
                  const docBackfillPreview = backfillPreview?.docId === doc.id ? backfillPreview : null;
                  const previewItem = docBackfillPreview?.item || {};
                  return (
                    <div key={doc.id} style={{padding:'12px 14px',borderBottom:'1px solid '+C.border}}>
                      <div style={{display:'flex',justifyContent:'space-between',gap:'10px',alignItems:'flex-start',flexWrap:'wrap'}}>
                        <div style={{flex:1,minWidth:'220px'}}>
                          <b style={{color:C.text,fontSize:'13px'}}>
                            {doc.type === 'warehouse' ? 'Накладная' : 'Счет/УПД'} № {doc.number || 'без номера'}
                          </b>
                          <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0'}}>
                            {(doc.date || 'без даты') + ' · ' + (doc.projectName || 'без объекта') + ' · ' + money(doc.amount)}
                          </p>
                          {linkedInvoice && <p style={{color:C.success,fontSize:'11px',margin:'2px 0'}}><Link2 size={11}/> Связано со счетом № {linkedInvoice.invoiceNumber || linkedInvoice.id}{supplierAmount ? ' · ' + money(supplierAmount) : ''}</p>}
                          {!doc.linked && <p style={{color:C.warning,fontSize:'11px',margin:'2px 0'}}><AlertTriangle size={11}/> Нет связанной первички поставщика</p>}
                          {doc.amountMismatch && <p style={{color:C.danger,fontSize:'11px',margin:'2px 0'}}>Сумма накладной расходится со счетом поставщика</p>}
                        </div>
                        <div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap',justifyContent:'flex-end'}}>
                          <span style={{color:C.textSec,fontSize:'11px'}}>{doc.status}</span>
                          {doc.type === 'warehouse' && !doc.linked && (
                            <button disabled={busy} onClick={event=>runBackfillForDoc(doc, event)} style={{...btnG,padding:'5px 9px',fontSize:'11px',opacity:busy?0.6:1}}>
                              <RefreshCw size={12}/>Связать первичку
                            </button>
                          )}
                          <button onClick={()=>setOpenedDoc(docOpen ? '' : doc.id)} style={{...btnB,padding:'5px 9px',fontSize:'11px'}}>
                            {docOpen ? <ChevronUp size={12}/> : <Eye size={12}/>}Открыть
                          </button>
                        </div>
                      </div>
                      {docBackfillPreview && (
                        <div onClick={event=>event.stopPropagation()} style={{marginTop:'10px',padding:'10px',borderRadius:'8px',backgroundColor:previewItem.needsReview?C.warningLight:C.successLight,border:'1px solid '+(previewItem.needsReview?C.warningBorder:C.successBorder)}}>
                          <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>Предпросмотр точечной сверки</b>
                          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(140px,1fr))',gap:'8px',marginBottom:'8px'}}>
                            <span style={{color:C.textSec,fontSize:'11px'}}>Накладная<br/><b style={{color:C.text}}>{previewItem.number || docBackfillPreview.fallbackNumber || docBackfillPreview.warehouseInvoiceId}</b></span>
                            <span style={{color:C.textSec,fontSize:'11px'}}>Дата<br/><b style={{color:C.text}}>{previewItem.date || doc.date || 'без даты'}</b></span>
                            <span style={{color:C.textSec,fontSize:'11px'}}>Объект<br/><b style={{color:C.text}}>{previewItem.projectName || doc.projectName || 'без объекта'}</b></span>
                            <span style={{color:C.textSec,fontSize:'11px'}}>Сумма<br/><b style={{color:C.text}}>{money(previewItem.amount || docBackfillPreview.fallbackAmount)}</b></span>
                          </div>
                          {previewItem.needsReview && (
                            <p style={{color:C.warning,fontSize:'12px',margin:'0 0 8px'}}>
                              После связи документ останется на ручной проверке: {previewItem.reviewReason || 'проверьте поставщика/документ'}
                            </p>
                          )}
                          <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 10px'}}>Склад и оплаты повторно не создаются. Apply будет выполнен только по этой накладной.</p>
                          <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                            <button disabled={busy} onClick={event=>applyBackfillPreview(docBackfillPreview, event)} style={{...btnG,padding:'7px 10px',fontSize:'12px',opacity:busy?0.6:1}}>Применить только эту</button>
                            <button disabled={busy} onClick={event=>{event.stopPropagation();setBackfillPreview(null);}} style={{...btnB,padding:'7px 10px',fontSize:'12px',opacity:busy?0.6:1}}>Отмена</button>
                          </div>
                        </div>
                      )}
                      {docOpen && (
                        <div style={{marginTop:'10px',paddingTop:'10px',borderTop:'1px dashed '+C.border}}>
                          <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginBottom:'10px'}}>
                            {(doc.photos || []).map((url, index) => (
                              <button key={url + index} onClick={()=>setShowPhotoModal && setShowPhotoModal(fileSrc ? fileSrc(url) : url)} style={{border:'1px solid '+C.border,background:C.bg,borderRadius:'8px',padding:'4px',cursor:'pointer'}}>
                                <img src={fileSrc ? fileSrc(url) : url} alt='' style={{width:'72px',height:'72px',objectFit:'cover',borderRadius:'6px',display:'block'}}/>
                              </button>
                            ))}
                            {!doc.photos?.length && <span style={{color:C.textMuted,fontSize:'12px'}}>Фото не прикреплено</span>}
                          </div>
                          {doc.items?.length ? (
                            <div style={{overflowX:'auto'}}>
                              <table style={{width:'100%',borderCollapse:'collapse',fontSize:'12px'}}>
                                <thead><tr><th style={{textAlign:'left',padding:'6px',color:C.textSec}}>Позиция</th><th style={{textAlign:'right',padding:'6px',color:C.textSec}}>Кол-во</th><th style={{textAlign:'right',padding:'6px',color:C.textSec}}>Сумма</th></tr></thead>
                                <tbody>
                                  {doc.items.slice(0, 80).map((item, idx) => {
                                    const total = Number(item.total || item.lineTotal || 0) || Number(item.quantity || 0) * Number(item.price || item.priceWithVat || 0);
                                    return (
                                      <tr key={idx} style={{borderTop:'1px solid '+C.border}}>
                                        <td style={{padding:'6px',color:C.text}}>{item.name || item.materialName || 'Материал'}</td>
                                        <td style={{padding:'6px',textAlign:'right',color:C.textSec}}>{Number(item.quantity || 0).toLocaleString('ru-RU') + ' ' + (item.unit || '')}</td>
                                        <td style={{padding:'6px',textAlign:'right',color:C.text}}>{money(total)}</td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p style={{color:C.textMuted,fontSize:'12px',margin:0}}><FileText size={12}/> Позиции есть только в связанном файле/счете или не распознаны.</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
