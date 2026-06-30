import React from 'react';
import { AlertTriangle, CheckCircle2, CreditCard, Eye, FileText, Link2, MessageSquare, Upload, XCircle } from 'lucide-react';
import { API } from '../api';
import DocumentRecognitionPanel from './DocumentRecognitionPanel';
import {
  ACCOUNTING_INVOICE_STATUSES,
  accountingStatusGroupLabels,
  buildAccountingInvoiceRows,
} from '../utils/accountingInvoices';

const statusTone = (status, C) => {
  if (status === 'Нет фото') return { color: C.danger, bg: C.dangerLight, border: C.dangerBorder };
  if (status === 'Нужно уточнение') return { color: C.warning, bg: C.warningLight, border: C.warningBorder };
  if (status === 'К оплате') return { color: C.accent, bg: C.accentLight, border: C.accentBorder };
  if (status === 'Частично оплачена') return { color: C.warning, bg: C.warningLight, border: C.warningBorder };
  if (status === 'Оплачена') return { color: C.success, bg: C.successLight, border: C.successBorder };
  if (status === 'Отклонена') return { color: C.danger, bg: C.dangerLight, border: C.dangerBorder };
  return { color: C.info || C.accent, bg: C.infoLight || C.accentLight, border: C.infoBorder || C.accentBorder };
};

const money = value => Math.round(Number(value || 0)).toLocaleString('ru-RU') + ' ₽';

export default function AccountingIncomingDocumentsPanel({
  C,
  card,
  btnO,
  btnG,
  btnB,
  btnR,
  btnGr,
  inp,
  invoices,
  supplierInvoices = [],
  warehouseInvoiceEstimateControl,
  fileSrc,
  setShowPhotoModal,
  showPreview,
  buildInvoiceContent,
  uploadPhoto,
  refreshData,
  badge,
  toNum,
}) {
  const [activeStatus, setActiveStatus] = React.useState('Нет фото');
  const [openedId, setOpenedId] = React.useState(null);
  const [busyId, setBusyId] = React.useState(null);

  const rows = React.useMemo(
    () => buildAccountingInvoiceRows(invoices, warehouseInvoiceEstimateControl),
    [invoices, warehouseInvoiceEstimateControl]
  );

  const supplierInvoiceById = React.useMemo(() => {
    const map = new Map();
    (supplierInvoices || []).forEach(invoice => map.set(String(invoice.id), invoice));
    return map;
  }, [supplierInvoices]);

  const counts = React.useMemo(() => {
    const base = Object.fromEntries(ACCOUNTING_INVOICE_STATUSES.map(status => [status, { count: 0, amount: 0 }]));
    rows.forEach(row => {
      if (!base[row.status]) base[row.status] = { count: 0, amount: 0 };
      base[row.status].count += 1;
      base[row.status].amount += row.status === 'Оплачена' ? row.paidAmount : row.debt || row.amount;
    });
    return base;
  }, [rows]);

  React.useEffect(() => {
    if (rows.length && activeStatus !== 'Все' && !rows.some(row => row.status === activeStatus)) {
      const next = ACCOUNTING_INVOICE_STATUSES.find(status => rows.some(row => row.status === status));
      if (next) setActiveStatus(next);
    }
  }, [rows, activeStatus]);

  const parseMoney = (value) => {
    const cleaned = String(value ?? '')
      .replace(/\u00a0/g, ' ')
      .replace(/\s/g, '')
      .replace(/₽/g, '')
      .replace(/руб(?:лей|ля|\.?)?/gi, '')
      .replace(/р\./gi, '')
      .replace(',', '.')
      .replace(/[^0-9.-]/g, '');
    const parsed = Number(cleaned);
    if (Number.isFinite(parsed)) return parsed;
    if (typeof toNum === 'function') return toNum(value);
    return 0;
  };

  const normalize = value => String(value || '').trim().toLowerCase();
  const supplierInvoiceAmount = invoice => Number(invoice?.amount || invoice?.totalAmount || 0);
  const supplierInvoiceTitle = invoice => {
    if (!invoice) return '';
    const number = invoice.invoiceNumber || invoice.id;
    const supplier = invoice.supplierName || 'поставщик не указан';
    return 'Счёт № ' + number + ' · ' + supplier + ' · ' + money(supplierInvoiceAmount(invoice));
  };

  const getLinkedSupplierInvoice = (row) => {
    const invoice = row.invoice || {};
    const directId = invoice.supplierInvoiceId || invoice.supplier_invoice_id;
    if (directId && supplierInvoiceById.has(String(directId))) {
      return supplierInvoiceById.get(String(directId));
    }
    return (supplierInvoices || []).find(supplierInvoice =>
      String(supplierInvoice.warehouseInvoiceId || supplierInvoice.warehouse_invoice_id || '') === String(invoice.id)
    );
  };

  const getSupplierInvoiceCandidates = (row) => {
    const invoice = row.invoice || {};
    const linked = getLinkedSupplierInvoice(row);
    const invoiceProject = normalize(invoice.project || (invoice.location === 'Основной склад' ? '' : invoice.location));
    const invoiceSupplier = normalize(invoice.supplierName);
    const amount = Number(row.amount || 0);
    const requestId = invoice.supplyRequestId || invoice.supply_request_id;
    return (supplierInvoices || [])
      .filter(supplierInvoice => {
        if (!supplierInvoice || supplierInvoice.status === 'Аннулирован') return false;
        if (linked && String(supplierInvoice.id) === String(linked.id)) return false;
        const linkedWarehouseId = supplierInvoice.warehouseInvoiceId || supplierInvoice.warehouse_invoice_id;
        if (linkedWarehouseId && String(linkedWarehouseId) !== String(invoice.id)) return false;
        if (requestId && supplierInvoice.requestId && String(supplierInvoice.requestId) === String(requestId)) return true;
        const supplierProject = normalize(supplierInvoice.projectName || supplierInvoice.project);
        const supplierName = normalize(supplierInvoice.supplierName);
        const sameProject = invoiceProject && supplierProject && invoiceProject === supplierProject;
        const sameSupplier = invoiceSupplier && supplierName && (invoiceSupplier === supplierName || invoiceSupplier.includes(supplierName) || supplierName.includes(invoiceSupplier));
        const supplierAmount = supplierInvoiceAmount(supplierInvoice);
        const closeAmount = amount > 0 && supplierAmount > 0 && Math.abs(amount - supplierAmount) <= Math.max(1, amount * 0.05);
        return sameProject && sameSupplier && closeAmount;
      })
      .slice(0, 3);
  };

  const updateAccounting = async (row, payload) => {
    setBusyId(row.invoice.id);
    try {
      const res = await fetch(API + '/warehouse-invoices/' + row.invoice.id + '/accounting', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.detail || data.error) {
        alert(data.detail || data.error || 'Не удалось обновить накладную');
        return false;
      }
      await refreshData();
      return true;
    } finally {
      setBusyId(null);
    }
  };

  const attachPhotos = async (row, fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const inv = row.invoice;
    const projectName = inv.project || (inv.location === 'Основной склад' ? 'Основной склад' : inv.location) || '';
    const urls = [];
    setBusyId(inv.id);
    try {
      for (const file of files) {
        const url = await uploadPhoto(file, { projectName, context: 'warehouse-invoices' });
        if (url) urls.push(url);
      }
    } finally {
      setBusyId(null);
    }
    if (!urls.length) {
      alert('Не удалось загрузить фото');
      return;
    }
    await updateAccounting(row, { photos: urls, accountingStatus: row.status === 'Нет фото' ? 'На проверке' : row.status });
  };

  const markStatus = async (row, status) => {
    const linkedSupplierInvoice = getLinkedSupplierInvoice(row);
    let comment = row.invoice.accountingComment || '';
    if (status === 'Нужно уточнение' || status === 'Отклонена') {
      const answer = window.prompt(status === 'Отклонена' ? 'Причина отклонения' : 'Что уточнить?', comment);
      if (answer === null) return;
      comment = answer;
    }
    const payload = { accountingStatus: status, accountingComment: comment };
    const linkedSupplierInvoiceId = linkedSupplierInvoice?.id || row.invoice.supplierInvoiceId;
    if (linkedSupplierInvoiceId) payload.supplierInvoiceId = linkedSupplierInvoiceId;
    await updateAccounting(row, payload);
  };

  const payInvoice = async (row) => {
    const linkedSupplierInvoice = getLinkedSupplierInvoice(row);
    const defaultAmount = Math.max(0, Number(row.debt || 0));
    if (defaultAmount <= 0.01) {
      await updateAccounting(row, { accountingStatus: 'Оплачена' });
      return;
    }
    const answer = window.prompt('Сумма оплаты', String(Math.round(defaultAmount * 100) / 100));
    if (!answer) return;
    const paymentAmount = parseMoney(answer);
    if (paymentAmount <= 0 || paymentAmount > defaultAmount + 0.01) {
      alert('Сумма должна быть от 0,01 до ' + money(defaultAmount));
      return;
    }
    const payload = {
      accountingStatus: paymentAmount + 0.01 >= defaultAmount ? 'Оплачена' : 'Частично оплачена',
      paymentAmount,
    };
    const linkedSupplierInvoiceId = linkedSupplierInvoice?.id || row.invoice.supplierInvoiceId;
    if (linkedSupplierInvoiceId) payload.supplierInvoiceId = linkedSupplierInvoiceId;
    await updateAccounting(row, payload);
  };

  const linkSupplierInvoice = async (row, supplierInvoice) => {
    if (!supplierInvoice?.id) return;
    await updateAccounting(row, { supplierInvoiceId: supplierInvoice.id });
  };

  const recognitionCommentFromResult = (result, current = '') => {
    const extracted = result?.extracted || {};
    const parts = [
      extracted.docType,
      extracted.number ? '№ ' + extracted.number : '',
      extracted.docDate ? 'от ' + extracted.docDate : '',
      extracted.counterpartyName,
      extracted.amount ? 'сумма ' + money(extracted.amount) : '',
      extracted.inn ? 'ИНН ' + extracted.inn : '',
      result?.fileUrl ? 'файл ' + result.fileUrl : '',
    ].filter(Boolean);
    if (!parts.length) return current || '';
    const line = 'Распознано: ' + parts.join('; ');
    const base = String(current || '').trim();
    if (base.includes(line)) return base;
    return base ? base + '\n' + line : line;
  };

  const applyRecognitionToAccounting = async (row, result) => {
    await updateAccounting(row, {
      accountingStatus: row.status === 'Нет фото' ? 'На проверке' : row.status,
      accountingComment: recognitionCommentFromResult(result, row.invoice.accountingComment),
    });
  };

  const filteredRows = activeStatus === 'Все' ? rows : rows.filter(row => row.status === activeStatus);
  const openedRow = rows.find(row => String(row.invoice.id) === String(openedId));

  const renderStatusBadge = (status) => {
    const tone = statusTone(status, C);
    return badge ? (
      <span style={badge(tone.color, tone.bg, tone.border)}>{status}</span>
    ) : (
      <span style={{ color: tone.color, backgroundColor: tone.bg, border: '1px solid ' + tone.border, borderRadius: '999px', padding: '4px 8px', fontSize: '11px', fontWeight: 800 }}>{status}</span>
    );
  };

  const renderActions = (row) => {
    const disabled = busyId === row.invoice.id;
    return (
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
        <button disabled={disabled} onClick={() => setOpenedId(openedId === row.invoice.id ? null : row.invoice.id)} style={{ ...btnB, padding: '6px 10px', fontSize: '11px' }}><Eye size={12} />Открыть</button>
        <label style={{ ...btnG, padding: '6px 10px', fontSize: '11px', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.6 : 1 }}>
          <Upload size={12} />Фото
          <input type="file" accept="image/*" multiple disabled={disabled} onChange={event => { attachPhotos(row, event.target.files); event.target.value = ''; }} style={{ display: 'none' }} />
        </label>
        {(row.status === 'На проверке' || row.status === 'Нужно уточнение') && (
          <button disabled={disabled || row.photos.length === 0} onClick={() => markStatus(row, 'К оплате')} style={{ ...btnGr, padding: '6px 10px', fontSize: '11px' }}><CheckCircle2 size={12} />К оплате</button>
        )}
        {(row.status === 'На проверке' || row.status === 'К оплате') && (
          <button disabled={disabled} onClick={() => markStatus(row, 'Нужно уточнение')} style={{ ...btnG, padding: '6px 10px', fontSize: '11px' }}><MessageSquare size={12} />Уточнить</button>
        )}
        {(row.status === 'К оплате' || row.status === 'Частично оплачена') && row.debt > 0 && (
          <button disabled={disabled} onClick={() => payInvoice(row)} style={{ ...btnO, padding: '6px 10px', fontSize: '11px' }}><CreditCard size={12} />Оплатить</button>
        )}
        {row.status !== 'Оплачена' && row.status !== 'Отклонена' && (
          <button disabled={disabled} onClick={() => markStatus(row, 'Отклонена')} style={{ ...btnR, padding: '6px 10px', fontSize: '11px' }}><XCircle size={12} /></button>
        )}
      </div>
    );
  };

  const renderDetail = (row) => {
    const inv = row.invoice;
    const linkedSupplierInvoice = getLinkedSupplierInvoice(row);
    const supplierInvoiceCandidates = getSupplierInvoiceCandidates(row);
    return (
      <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: C.bg, border: '1.5px solid ' + C.accentBorder }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '12px' }}>
          <div>
            <b style={{ color: C.text, fontSize: '15px' }}>Накладная № {inv.number || inv.id}</b>
            <p style={{ color: C.textSec, fontSize: '12px', margin: '4px 0 0' }}>{inv.supplierName || 'Поставщик не указан'} · {inv.date || 'без даты'} · {inv.project || inv.location || 'без объекта'}</p>
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {renderStatusBadge(row.status)}
            {row.issueRows.length > 0 && <span style={badge ? badge(C.warning, C.warningLight, C.warningBorder) : { color: C.warning }}>{'Замечаний ' + row.issueRows.length}</span>}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: '10px', marginBottom: '12px' }}>
          <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 3px' }}>Сумма</p><b style={{ color: C.text }}>{money(row.amount)}</b></div>
          <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 3px' }}>Оплачено</p><b style={{ color: row.paidAmount > 0 ? C.success : C.textMuted }}>{money(row.paidAmount)}</b></div>
          <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 3px' }}>Фото</p><b style={{ color: row.photos.length ? C.success : C.danger }}>{row.photos.length || 'нет'}</b></div>
          <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 3px' }}>Строки</p><b style={{ color: C.text }}>{row.controls.length || (inv.items || []).length}</b></div>
        </div>

        <div style={{ padding: '10px', borderRadius: '8px', border: '1px solid ' + C.border, backgroundColor: C.bgAlt, marginBottom: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <b style={{ color: C.text, fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}><Link2 size={13} />Счёт поставщика</b>
            {linkedSupplierInvoice ? (
              <span style={{ color: C.success, backgroundColor: C.successLight, border: '1px solid ' + C.successBorder, borderRadius: '999px', padding: '4px 8px', fontSize: '11px', fontWeight: 800 }}>связан</span>
            ) : <span style={{ color: C.warning, fontSize: '11px', fontWeight: 800 }}>не связан</span>}
          </div>
          {linkedSupplierInvoice ? (
            <p style={{ color: C.textSec, fontSize: '12px', margin: '6px 0 0' }}>
              {supplierInvoiceTitle(linkedSupplierInvoice)} · {linkedSupplierInvoice.status || 'без статуса'}
            </p>
          ) : supplierInvoiceCandidates.length ? (
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '8px' }}>
              {supplierInvoiceCandidates.map(candidate => (
                <button key={candidate.id} disabled={busyId === inv.id} onClick={() => linkSupplierInvoice(row, candidate)} style={{ ...btnB, padding: '6px 10px', fontSize: '11px' }}>
                  <Link2 size={12} />Связать: {candidate.invoiceNumber || candidate.id}
                </button>
              ))}
            </div>
          ) : (
            <p style={{ color: C.textMuted, fontSize: '12px', margin: '6px 0 0' }}>Подходящий счёт не найден. Создайте счёт из КП или проверьте поставщика/сумму.</p>
          )}
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
          {row.photos.map((url, index) => (
            <img key={url + index} src={fileSrc ? fileSrc(url) : url} alt="" onClick={() => setShowPhotoModal && setShowPhotoModal(fileSrc ? fileSrc(url) : url)} style={{ width: '72px', height: '72px', objectFit: 'cover', borderRadius: '8px', border: '1px solid ' + C.border, cursor: 'pointer' }} />
          ))}
          <label style={{ ...btnG, minHeight: '72px', padding: '8px 12px', cursor: 'pointer', alignItems: 'center' }}>
            <Upload size={13} />Добавить фото
            <input type="file" accept="image/*" multiple onChange={event => { attachPhotos(row, event.target.files); event.target.value = ''; }} style={{ display: 'none' }} />
          </label>
        </div>

        <DocumentRecognitionPanel
          C={C}
          card={card}
          inp={inp}
          btnG={btnG}
          btnO={btnO}
          btnB={btnB}
          uploadPhoto={uploadPhoto}
          fileSrc={fileSrc}
          projectName={inv.project || inv.location || 'Бухгалтерская первичка'}
          context="accounting-incoming-documents"
          entityType="accounting_invoice"
          currentFields={inv}
          onApplyExtracted={result => applyRecognitionToAccounting(row, result)}
          applyExtractedLabel="Добавить в комментарий"
        />

        <div style={{ display: 'grid', gap: '6px', marginBottom: '12px' }}>
          {(row.controls.length ? row.controls : (inv.items || [])).slice(0, 12).map((item, index) => {
            const sourceItem = row.controls.length ? item : {};
            const name = item.canonicalName || item.name || sourceItem.name || '';
            const qty = item.incomingText || [item.quantity, item.unit].filter(Boolean).join(' ');
            const lineSum = item.lineSumText || (item.lineSum ? money(item.lineSum) : '');
            return (
              <div key={index} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '8px', alignItems: 'center', padding: '8px', borderRadius: '8px', border: '1px solid ' + C.border, backgroundColor: C.bgAlt }}>
                <b style={{ color: C.text, fontSize: '12px' }}>{name}</b>
                <span style={{ color: C.textSec, fontSize: '11px' }}>{qty || '—'}</span>
                <span style={{ color: C.textSec, fontSize: '11px' }}>{lineSum || '—'}</span>
                {sourceItem.status ? renderStatusBadge(sourceItem.status) : null}
              </div>
            );
          })}
        </div>

        {inv.accountingComment && <p style={{ color: C.textSec, fontSize: '12px', margin: '0 0 12px' }}>Комментарий: {inv.accountingComment}</p>}
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
          {renderActions(row)}
          {showPreview && buildInvoiceContent && <button onClick={() => showPreview(buildInvoiceContent(inv), 'Накладная № ' + (inv.number || inv.id))} style={{ ...btnB, padding: '6px 10px', fontSize: '11px' }}><FileText size={12} />Печать</button>}
        </div>
      </div>
    );
  };

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(145px,1fr))', gap: '10px', marginBottom: '14px' }}>
        {[...ACCOUNTING_INVOICE_STATUSES, 'Все'].map(status => {
          const isAll = status === 'Все';
          const stat = isAll
            ? { count: rows.length, amount: rows.reduce((sum, row) => sum + (row.status === 'Оплачена' ? row.paidAmount : row.debt || row.amount), 0) }
            : counts[status] || { count: 0, amount: 0 };
          const tone = isAll ? { color: C.text, bg: C.bg, border: C.border } : statusTone(status, C);
          return (
            <button key={status} onClick={() => setActiveStatus(status)} style={{ textAlign: 'left', cursor: 'pointer', padding: '12px', borderRadius: '8px', border: '1.5px solid ' + (activeStatus === status ? tone.color : tone.border), backgroundColor: tone.bg, color: tone.color }}>
              <p style={{ margin: '0 0 5px', fontSize: '11px', fontWeight: 800 }}>{isAll ? 'Все документы' : accountingStatusGroupLabels[status]}</p>
              <b style={{ fontSize: '16px' }}>{stat.count}</b>
              <span style={{ display: 'block', marginTop: '3px', fontSize: '11px', color: tone.color }}>{money(stat.amount)}</span>
            </button>
          );
        })}
      </div>

      <div style={{ ...card, padding: '12px', marginBottom: '14px', backgroundColor: C.bg }}>
        <b style={{ color: C.text, fontSize: '14px' }}>Входящие документы · {activeStatus === 'Все' ? 'все' : accountingStatusGroupLabels[activeStatus]}</b>
      </div>

      {openedRow && renderDetail(openedRow)}

      {filteredRows.length === 0 ? (
        <div style={{ ...card, padding: '28px', textAlign: 'center', color: C.textMuted }}>Документов нет</div>
      ) : (
        <div style={{ display: 'grid', gap: '10px' }}>
          {filteredRows.map(row => {
            const inv = row.invoice;
            const tone = statusTone(row.status, C);
            const linkedSupplierInvoice = getLinkedSupplierInvoice(row);
            return (
              <div key={inv.id} style={{ ...card, padding: '14px', border: '1.5px solid ' + tone.border, backgroundColor: C.bg }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: '12px', alignItems: 'start' }}>
                  <div>
                    <b style={{ color: C.text, fontSize: '13px' }}>№ {inv.number || inv.id} · {inv.date || 'без даты'}</b>
                    <p style={{ color: C.textSec, fontSize: '12px', margin: '3px 0 0' }}>{inv.supplierName || 'Поставщик не указан'}</p>
                    <p style={{ color: C.textMuted, fontSize: '11px', margin: '3px 0 0' }}>{inv.project || inv.location || 'без объекта'} · фото {row.photos.length} · строк {(inv.items || []).length || row.controls.length}</p>
                    <p style={{ color: linkedSupplierInvoice ? C.success : C.warning, fontSize: '11px', margin: '3px 0 0', fontWeight: 800 }}>
                      {linkedSupplierInvoice ? 'Счёт связан: № ' + (linkedSupplierInvoice.invoiceNumber || linkedSupplierInvoice.id) : 'Счёт поставщика не связан'}
                    </p>
                  </div>
                  <div>
                    <p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Сумма / долг</p>
                    <b style={{ color: C.text, fontSize: '13px' }}>{money(row.amount)}</b>
                    {row.debt > 0 && row.paidAmount > 0 && <p style={{ color: C.warning, fontSize: '11px', margin: '3px 0 0' }}>долг {money(row.debt)}</p>}
                  </div>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    {renderStatusBadge(row.status)}
                    {row.issueRows.length > 0 && <span style={{ color: C.warning, backgroundColor: C.warningLight, border: '1px solid ' + C.warningBorder, borderRadius: '999px', padding: '4px 8px', fontSize: '10px', fontWeight: 800 }}><AlertTriangle size={11} style={{ verticalAlign: 'middle', marginRight: '3px' }} />{row.issueRows.length}</span>}
                  </div>
                </div>
                <div style={{ marginTop: '10px' }}>{renderActions(row)}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
