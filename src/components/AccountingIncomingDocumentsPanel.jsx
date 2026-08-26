import React from 'react';
import { AlertTriangle, CheckCircle2, CreditCard, Eye, FileText, Link2, MessageSquare, Upload, XCircle } from 'lucide-react';
import { API } from '../api';
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
  suppliers = [],
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
  const [visibleRows, setVisibleRows] = React.useState(30);
  const [selectedSupplierByInvoice, setSelectedSupplierByInvoice] = React.useState({});
  const [supplierRecoveryId, setSupplierRecoveryId] = React.useState(null);
  const [supplierResolutionBusyId, setSupplierResolutionBusyId] = React.useState(null);
  const [supplierResolutionErrors, setSupplierResolutionErrors] = React.useState({});
  const rowsStep = 30;

  const rows = React.useMemo(
    () => buildAccountingInvoiceRows(invoices, warehouseInvoiceEstimateControl, { includeControls: false }),
    [invoices, warehouseInvoiceEstimateControl]
  );

  const enrichRow = React.useCallback((row) => {
    if (!row) return row;
    const controls = typeof warehouseInvoiceEstimateControl === 'function'
      ? (warehouseInvoiceEstimateControl(row.invoice) || []).filter(control => control && control.name)
      : [];
    return {
      ...row,
      controls,
      issueRows: controls.filter(control => ['danger', 'warning'].includes(control.severity)),
    };
  }, [warehouseInvoiceEstimateControl]);

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
  const normalizeSupplierName = value => normalize(value)
    .replace(/[«»"'`]/g, '')
    .replace(/[.,]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
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

  const getSupplierDocumentUrls = (row) => {
    const linked = getLinkedSupplierInvoice(row);
    return [...new Set([
      linked?.fileUrl,
      linked?.file_url,
      linked?.photoUrl,
      linked?.photo_url,
      linked?.deliveryDocumentUrl,
      linked?.delivery_document_url,
      linked?.deliveryPhotoUrl,
      linked?.delivery_photo_url,
      ...(row.photos || []),
    ].filter(Boolean).map(String))];
  };

  const getExactExistingSupplier = (row) => {
    const linked = getLinkedSupplierInvoice(row);
    const documentNames = new Set([
      row.invoice?.supplierName,
      row.invoice?.supplier_name,
      linked?.supplierName,
      linked?.supplier_name,
    ].map(normalizeSupplierName).filter(Boolean));
    if (!documentNames.size) return null;
    const matches = (suppliers || []).filter(supplier =>
      Number(supplier?.id || 0) > 0
      && documentNames.has(normalizeSupplierName(supplier?.name))
    );
    return matches.length === 1 ? matches[0] : null;
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
    } catch (error) {
      alert('Не удалось связаться с сервером. Проверьте интернет и повторите.');
      return false;
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

  const linkSupplier = async (row) => {
    const supplierId = Number(selectedSupplierByInvoice[row.invoice.id] || 0);
    if (supplierId <= 0) return;
    const linked = await updateAccounting(row, { supplierId });
    if (linked) {
      setSelectedSupplierByInvoice(current => ({ ...current, [row.invoice.id]: '' }));
      setSupplierRecoveryId(null);
      setSupplierResolutionErrors(current => ({ ...current, [row.invoice.id]: '' }));
    }
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

  const supplierRequisitesFromRecognition = (extracted, fallbackName = '') => ({
    name: extracted?.counterpartyName || extracted?.supplierName || extracted?.supplier || fallbackName || '',
    inn: extracted?.inn || extracted?.supplierInn || extracted?.supplier_inn || '',
    kpp: extracted?.kpp || extracted?.supplierKpp || extracted?.supplier_kpp || '',
    ogrn: extracted?.ogrn || extracted?.supplierOgrn || extracted?.supplier_ogrn || '',
    legalAddress: extracted?.legalAddress || '',
    bank: extracted?.bank || '',
    bik: extracted?.bik || '',
    bankAccount: extracted?.bankAccount || '',
    corrAccount: extracted?.corrAccount || '',
    signerName: extracted?.signerName || '',
    signerBasis: extracted?.signerBasis || '',
  });

  const blobAsDataUrl = blob => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('Не удалось прочитать фото накладной'));
    reader.readAsDataURL(blob);
  });

  const resolveSupplierAndMarkForPayment = async row => {
    const invoiceId = row.invoice.id;
    setOpenedId(invoiceId);
    setSupplierResolutionBusyId(invoiceId);
    setSupplierResolutionErrors(current => ({ ...current, [invoiceId]: '' }));
    const linkedSupplierInvoice = getLinkedSupplierInvoice(row);
    const exactSupplier = getExactExistingSupplier(row);
    if (exactSupplier) {
      const payload = {
        accountingStatus: 'К оплате',
        supplierId: Number(exactSupplier.id),
      };
      const linkedSupplierInvoiceId = linkedSupplierInvoice?.id || row.invoice.supplierInvoiceId;
      if (linkedSupplierInvoiceId) payload.supplierInvoiceId = linkedSupplierInvoiceId;
      const updated = await updateAccounting(row, payload);
      if (updated) {
        setSupplierRecoveryId(null);
        setSupplierResolutionErrors(current => ({ ...current, [invoiceId]: '' }));
      }
      else {
        setSupplierRecoveryId(invoiceId);
        setSupplierResolutionErrors(current => ({ ...current, [invoiceId]: 'Сервер не смог связать поставщика. Выберите его из списка.' }));
      }
      setSupplierResolutionBusyId(null);
      return;
    }
    const documentUrls = getSupplierDocumentUrls(row);
    if (!documentUrls.length) {
      setSupplierRecoveryId(invoiceId);
      setSupplierResolutionErrors(current => ({ ...current, [invoiceId]: 'У накладной и связанного счёта нет доступного файла.' }));
      setSupplierResolutionBusyId(null);
      return;
    }
    setBusyId(invoiceId);
    try {
      let documentBlob = null;
      for (const documentUrl of documentUrls) {
        try {
          const response = await fetch(fileSrc ? fileSrc(documentUrl) : documentUrl, {
            credentials: 'include',
            cache: 'no-store',
          });
          if (!response.ok) continue;
          const blob = await response.blob();
          if (!blob.size || blob.size > 15 * 1024 * 1024) continue;
          documentBlob = blob;
          break;
        } catch (_error) {
          // The warehouse photo may be stale. Continue with the linked supplier document.
        }
      }
      if (!documentBlob) throw new Error('Не удалось открыть файл накладной или связанного счёта');
      const image = await blobAsDataUrl(documentBlob);
      const scanResponse = await fetch(API + '/scan-invoice', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          image,
          target: 'warehouse',
          location: row.invoice.location || row.invoice.project || '',
          project: row.invoice.project || '',
          warehouseTarget: row.invoice.project ? 'object' : 'main',
          selectedAction: 'receive_to_warehouse',
          sourceType: 'accounting_supplier_resolution',
        }),
      });
      const scanResult = await scanResponse.json().catch(() => ({}));
      if (!scanResponse.ok || !scanResult.ok) {
        throw new Error(scanResult.detail || scanResult.error || 'Не удалось распознать поставщика');
      }
      const extracted = scanResult.data || {};
      const supplierRequisites = supplierRequisitesFromRecognition(extracted, row.invoice.supplierName);
      const inn = String(supplierRequisites.inn || '').replace(/\D/g, '');
      const ogrn = String(supplierRequisites.ogrn || '').replace(/\D/g, '');
      if (![10, 12].includes(inn.length) && ![13, 15].includes(ogrn.length)) {
        throw new Error('На фото не удалось прочитать ИНН или ОГРН поставщика');
      }
      const payload = {
        accountingStatus: 'К оплате',
        accountingComment: recognitionCommentFromResult({
          extracted: {
            counterpartyName: supplierRequisites.name,
            inn: supplierRequisites.inn,
            kpp: supplierRequisites.kpp,
            ogrn: supplierRequisites.ogrn,
          },
        }, row.invoice.accountingComment),
        supplierRequisites,
      };
      const linkedSupplierInvoiceId = linkedSupplierInvoice?.id || row.invoice.supplierInvoiceId;
      if (linkedSupplierInvoiceId) payload.supplierInvoiceId = linkedSupplierInvoiceId;
      const updated = await updateAccounting(row, payload);
      if (updated) {
        setSupplierRecoveryId(null);
        setSupplierResolutionErrors(current => ({ ...current, [invoiceId]: '' }));
      } else {
        setSupplierRecoveryId(invoiceId);
        setSupplierResolutionErrors(current => ({ ...current, [invoiceId]: 'Сервер не смог перевести накладную в статус «К оплате».' }));
      }
    } catch (error) {
      setSupplierRecoveryId(invoiceId);
      setSupplierResolutionErrors(current => ({
        ...current,
        [invoiceId]: (error && error.message) || 'Не удалось определить поставщика.',
      }));
    } finally {
      setBusyId(null);
      setSupplierResolutionBusyId(null);
    }
  };

  const filteredRows = activeStatus === 'Все' ? rows : rows.filter(row => row.status === activeStatus);
  const visibleBaseRows = filteredRows.slice(0, visibleRows);
  const hiddenRows = Math.max(0, filteredRows.length - visibleBaseRows.length);
  const displayedRows = React.useMemo(
    () => visibleBaseRows.map(enrichRow),
    [visibleBaseRows, enrichRow],
  );
  const openedBaseRow = rows.find(row => String(row.invoice.id) === String(openedId));
  const openedRow = React.useMemo(() => enrichRow(openedBaseRow), [openedBaseRow, enrichRow]);

  React.useEffect(() => {
    setVisibleRows(30);
  }, [activeStatus, invoices?.length]);

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
    const linkedSupplierInvoice = getLinkedSupplierInvoice(row);
    const supplierId = Number(
      row.invoice.supplierId
      || row.invoice.supplier_id
      || linkedSupplierInvoice?.supplierId
      || linkedSupplierInvoice?.supplier_id
      || 0,
    );
    const paymentBlocked = supplierId <= 0;
    const supplierResolutionPending = String(supplierResolutionBusyId) === String(row.invoice.id) && paymentBlocked;
    const paymentBlockedTitle = paymentBlocked
      ? 'Система прочитает ИНН/ОГРН, найдёт или создаст поставщика и свяжет документы'
      : '';
    return (
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
        <button disabled={disabled} onClick={() => setOpenedId(openedId === row.invoice.id ? null : row.invoice.id)} style={{ ...btnB, padding: '6px 10px', fontSize: '11px' }}><Eye size={12} />Открыть</button>
        {row.photos.length === 0 && (
          <label style={{ ...btnG, padding: '6px 10px', fontSize: '11px', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.6 : 1 }}>
            <Upload size={12} />Добавить фото
            <input type="file" accept="image/*" multiple disabled={disabled} onChange={event => { attachPhotos(row, event.target.files); event.target.value = ''; }} style={{ display: 'none' }} />
          </label>
        )}
        {(row.status === 'На проверке' || row.status === 'Нужно уточнение') && (
          <button
            title={paymentBlockedTitle}
            disabled={disabled || row.photos.length === 0}
            onClick={() => paymentBlocked ? resolveSupplierAndMarkForPayment(row) : markStatus(row, 'К оплате')}
            style={{ ...btnGr, padding: '6px 10px', fontSize: '11px', opacity: disabled || row.photos.length === 0 ? 0.6 : 1, cursor: disabled || row.photos.length === 0 ? 'not-allowed' : 'pointer' }}
          ><CheckCircle2 size={12} />{supplierResolutionPending ? 'Определяем поставщика…' : 'К оплате'}</button>
        )}
        {(row.status === 'На проверке' || row.status === 'К оплате') && (
          <button disabled={disabled} onClick={() => markStatus(row, 'Нужно уточнение')} style={{ ...btnG, padding: '6px 10px', fontSize: '11px' }}><MessageSquare size={12} />Уточнить</button>
        )}
        {(row.status === 'К оплате' || row.status === 'Частично оплачена') && row.debt > 0 && (
          <button title={paymentBlockedTitle} disabled={disabled || paymentBlocked} onClick={() => payInvoice(row)} style={{ ...btnO, padding: '6px 10px', fontSize: '11px' }}><CreditCard size={12} />Оплатить</button>
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
    const hasSupplier = Number(inv.supplierId || inv.supplier_id || linkedSupplierInvoice?.supplierId || linkedSupplierInvoice?.supplier_id || 0) > 0;
    const showSupplierRecovery = !hasSupplier && String(supplierRecoveryId) === String(inv.id);
    const supplierResolutionPending = !hasSupplier && String(supplierResolutionBusyId) === String(inv.id);
    const supplierResolutionError = supplierResolutionErrors[inv.id] || '';
    const supplierOptions = (suppliers || [])
      .filter(supplier => Number(supplier?.id || 0) > 0)
      .sort((left, right) => String(left.name || '').localeCompare(String(right.name || ''), 'ru'));
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
            <>
              <p style={{ color: C.textSec, fontSize: '12px', margin: '6px 0 0' }}>
                {supplierInvoiceTitle(linkedSupplierInvoice)} · {linkedSupplierInvoice.status || 'без статуса'}
              </p>
              {!hasSupplier && (
                <p style={{ color: C.success, fontSize: '11px', margin: '5px 0 0' }}>
                  Поставщик определится автоматически при нажатии «К оплате».
                </p>
              )}
            </>
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

        {supplierResolutionPending && (
          <div role="status" aria-live="polite" style={{ padding: '10px', borderRadius: '8px', border: '1px solid ' + C.infoBorder, backgroundColor: C.infoLight, color: C.info, fontSize: '12px', fontWeight: 800, marginBottom: '12px' }}>
            Читаем связанный счёт и определяем поставщика…
          </div>
        )}

        {showSupplierRecovery && (
          <div style={{ padding: '10px', borderRadius: '8px', border: '1px solid ' + C.warningBorder, backgroundColor: C.warningLight, marginBottom: '12px' }}>
            <b style={{ color: C.warning, fontSize: '12px', display: 'block', marginBottom: '5px' }}>Не удалось прочитать документ</b>
            <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 8px' }}>{supplierResolutionError || 'Загрузите читаемое фото или выберите поставщика.'}</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px,1fr) auto', gap: '8px', alignItems: 'center' }}>
              <select
                value={selectedSupplierByInvoice[inv.id] || ''}
                onChange={event => setSelectedSupplierByInvoice(current => ({ ...current, [inv.id]: event.target.value }))}
                style={{ ...inp, marginBottom: 0 }}
              >
                <option value="">Выберите поставщика</option>
                {supplierOptions.map(supplier => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.name}{supplier.inn ? ' · ИНН ' + supplier.inn : ''}
                  </option>
                ))}
              </select>
              <button
                disabled={busyId === inv.id || !selectedSupplierByInvoice[inv.id]}
                onClick={() => linkSupplier(row)}
                style={{ ...btnB, padding: '9px 12px' }}
              ><Link2 size={13} />Связать поставщика</button>
            </div>
            <label style={{ ...btnG, display: 'inline-flex', marginTop: '8px', padding: '8px 10px', cursor: 'pointer' }}>
              <Upload size={13} />Заменить фото
              <input type="file" accept="image/*" multiple onChange={event => { attachPhotos(row, event.target.files); event.target.value = ''; }} style={{ display: 'none' }} />
            </label>
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: showSupplierRecovery ? '12px' : 0 }}>
          {row.photos.map((url, index) => (
            <img key={url + index} src={fileSrc ? fileSrc(url) : url} alt="" onClick={() => setShowPhotoModal && setShowPhotoModal(fileSrc ? fileSrc(url) : url)} style={{ width: '72px', height: '72px', objectFit: 'cover', borderRadius: '8px', border: '1px solid ' + C.border, cursor: 'pointer' }} />
          ))}
        </div>

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
          {displayedRows.map(row => {
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
          {hiddenRows > 0 && (
            <button
              type="button"
              onClick={() => setVisibleRows(limit => Math.min(filteredRows.length, limit + rowsStep))}
              style={{ ...btnG, width: '100%', justifyContent: 'center', marginTop: '4px' }}
            >
              Показать ещё {Math.min(hiddenRows, rowsStep)} документов
            </button>
          )}
        </div>
      )}
    </div>
  );
}
