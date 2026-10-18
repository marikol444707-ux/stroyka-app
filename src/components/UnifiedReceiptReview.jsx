import React from 'react';
import SupplyFileLink from '../features/supply/SupplyFileLink';

const documentType = parsed => (parsed.documentType || parsed.document_type) === 'universal_transfer_document' ? 'upd' : (parsed.documentType || parsed.document_type || '');
export const receiptPayload = ({ parsed = {}, originalUrls = [], location = '', companyId, projectId, sourceSupplierInvoiceId, selectedBatchId, explicitSelectionConfirmed }) => {
  const type = documentType(parsed);
  return {
    document: {
      documentType: type,
      ...(type === 'payment_invoice' ? {
        invoiceNumber: parsed.invoiceNumber || parsed.invoice_number || parsed.number || '',
        invoiceDate: parsed.invoiceDate || parsed.invoice_date || parsed.date || '',
      } : {
        waybillNumber: parsed.waybillNumber || parsed.number || parsed.invoiceNumber || '',
        waybillDate: parsed.waybillDate || parsed.date || parsed.invoiceDate || '',
      }),
      supplierInn: parsed.supplierInn || parsed.supplier_inn || '',
      buyerInn: parsed.buyerInn || parsed.buyer_inn || '',
      lines: (parsed.lines || parsed.items || []).map(item => ({ materialName: item.materialName || item.name || '', unit: item.unit || '', quantity: item.quantity })),
    },
    originalUrls,
    ...(companyId != null ? { companyId } : {}),
    ...(projectId != null ? { projectId } : {}),
    ...(location && location !== 'Основной склад' ? { project: location } : {}),
    ...(sourceSupplierInvoiceId != null ? { sourceSupplierInvoiceId } : {}),
    ...(selectedBatchId != null ? { selectedBatchId, explicitSelectionConfirmed: explicitSelectionConfirmed === true } : {}),
  };
};
const positiveId = value => Number.isSafeInteger(Number(value)) && Number(value) > 0;
const accepted = line => Boolean(line.receivedAt || line.warehouseInvoiceId) || ['Принято', 'Проблема'].includes(line.status);

export default function UnifiedReceiptReview({ API, scan, onNewDocument, onConfirmed, onOpenReceipt, onCancel, onDifferentDocument, onWaybillRequired }) {
  const initialPayload = React.useMemo(() => receiptPayload(scan), [scan]);
  const [payload, setPayload] = React.useState(initialPayload);
  const [documentDraft, setDocumentDraft] = React.useState(initialPayload.document);
  React.useEffect(() => { setPayload(initialPayload); setDocumentDraft(initialPayload.document); }, [initialPayload]);
  const [result, setResult] = React.useState(null);
  const [error, setError] = React.useState('');
  const [actual, setActual] = React.useState({});
  const [confirmed, setConfirmed] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [complete, setComplete] = React.useState(false);
  const [selectedCandidate, setSelectedCandidate] = React.useState('');
  const [selectionConfirmed, setSelectionConfirmed] = React.useState(false);
  const submitting = React.useRef(false);
  const choosing = React.useRef(false);
  const generation = React.useRef(0);
  React.useEffect(() => {
    const token = generation;
    const current = ++token.current;
    setResult(null); setError(''); setActual({}); setConfirmed(false); setComplete(false); setBusy(false);
    setSelectedCandidate(''); setSelectionConfirmed(false); choosing.current = false;
    if (!payload.originalUrls.length) { setError('Оригинал документа не загружен. Приёмка заблокирована.'); return; }
    fetch(API + '/warehouse-receipts/resolve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      .then(async response => { const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось сверить документ'); return data; })
      .then(data => { if (current === generation.current) setResult(data); })
      .catch(err => { if (current === generation.current) setError(err.message); });
    return () => { token.current++; };
  }, [API, payload]);
  const paymentDocument = initialPayload.document.documentType === 'payment_invoice' || documentDraft.documentType === 'payment_invoice';
  const documentChanged = documentDraft !== payload.document;
  const candidates = (result?.candidateBatches || []).filter(candidate => positiveId(candidate.id)
    && (payload.companyId == null || candidate.companyId == null || String(candidate.companyId) === String(payload.companyId))
    && (payload.sourceSupplierInvoiceId == null || String(candidate.sourceSupplierInvoiceId) === String(payload.sourceSupplierInvoiceId)));
  const chosenCandidate = candidates.find(candidate => String(candidate.id) === selectedCandidate);
  const sourceChoice = result?.status === 'source_selection';
  const canChoose = Boolean(chosenCandidate && selectionConfirmed && !documentChanged && !busy
    && (!sourceChoice || (positiveId(chosenCandidate.sourceSupplierInvoiceId) && onWaybillRequired)));
  const chooseCandidate = () => {
    if (!canChoose || choosing.current) return;
    choosing.current = true;
    const selection = { selectedBatchId: Number(chosenCandidate.id), explicitSelectionConfirmed: true,
      ...(positiveId(chosenCandidate.sourceSupplierInvoiceId) ? { sourceSupplierInvoiceId: Number(chosenCandidate.sourceSupplierInvoiceId) } : {}) };
    generation.current++;
    setResult(null); setConfirmed(false); setActual({});
    if (sourceChoice) {
      onWaybillRequired({ ...selection, sourceInvoiceOriginalUrls: payload.originalUrls, sourceInvoiceDocument: payload.document });
    } else {
      setPayload({ ...payload, ...selection });
    }
  };
  const lines = result?.matchedBatch?.lines || [];
  const remaining = lines.filter(line => !accepted(line));
  const matchedLocation = result?.matchedBatch?.project || payload.project || 'Основной склад';
  const destinationMismatch = Boolean(payload.project && result?.matchedBatch?.project && payload.project !== result.matchedBatch.project);
  const valid = remaining.length > 0 && remaining.every(line => {
    const value = actual[line.id]?.receivedQuantity;
    return value !== undefined && String(value).trim() !== '' && Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= Number(line.shippedQuantity);
  });
  const change = (id, key, value) => setActual(prev => ({ ...prev, [id]: { ...prev[id], [key]: value } }));
  const submit = async () => {
    if (paymentDocument || destinationMismatch || submitting.current || complete || !confirmed || !valid || documentDraft !== payload.document || result?.status !== 'match') return;
    submitting.current = true; setBusy(true); setError('');
    const current = generation.current;
    try {
      const response = await fetch(API + '/warehouse-receipts/confirm', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...payload, physicalReceiptConfirmed: true, actualLines: remaining.map(line => ({ deliveryId: line.id, receivedQuantity: Number(actual[line.id].receivedQuantity), qualityStatus: actual[line.id].qualityStatus || 'Принято', qualityNotes: actual[line.id].qualityNotes || '', claimDescription: actual[line.id].claimDescription || '' })) }) });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось подтвердить приёмку');
      if (current !== generation.current) return;
      setComplete(true); onConfirmed?.(data);
    } catch (err) { if (current === generation.current) setError(err.message); }
    finally { submitting.current = false; if (current === generation.current) setBusy(false); }
  };
  const editDocument = (key, value) => {
    setConfirmed(false); setSelectionConfirmed(false); setSelectedCandidate('');
    setDocumentDraft(prev => key === 'documentType' && value === 'payment_invoice'
      ? { ...prev, documentType: value, invoiceNumber: prev.invoiceNumber || '', invoiceDate: prev.invoiceDate || '', waybillNumber: '', waybillDate: '' }
      : { ...prev, [key]: value });
  };
  const editLine = (index, key, value) => {
    setConfirmed(false); setSelectionConfirmed(false); setSelectedCandidate('');
    setDocumentDraft(prev => ({...prev, lines:prev.lines.map((line, i) => i === index ? {...line,[key]:value} : line)}));
  };
  return <section aria-label="Сверка физической приёмки" style={{display:'grid',gap:10}}>
    <h3>Проверка документа и фактической поставки</h3>
    <p>Оригиналов сохранено: {payload.originalUrls.length}. Распознавание не создаёт приход.</p>
    {scan.recognitionError && <p role="alert">{scan.recognitionError} Оригиналы сохранены. Перенесите реквизиты и строки вручную, затем повторите проверку.</p>}
    {!complete && !busy && result?.status !== 'existing_receipt' && !(result?.status === 'match' && !remaining.length) && <details open={Boolean(scan.recognitionError)}>
      <summary>Проверить или исправить распознанные реквизиты и строки</summary>
      <p>Изменения не создают приход. Сверьте данные с оригиналом.</p>
      <label>Тип документа<select aria-label="Тип документа" disabled={initialPayload.document.documentType === 'payment_invoice'} value={documentDraft.documentType} onChange={e=>editDocument('documentType',e.target.value)}>
        <option value="">Выберите тип</option><option value="waybill">Накладная</option><option value="delivery_note">Товарная накладная</option><option value="upd">УПД</option><option value="payment_invoice">Счёт на оплату</option>
      </select></label>
      {[...(documentDraft.documentType === 'payment_invoice' ? [['invoiceNumber','Номер счёта'],['invoiceDate','Дата счёта']] : [['waybillNumber','Номер документа'],['waybillDate','Дата документа']]),['supplierInn','ИНН поставщика'],['buyerInn','ИНН покупателя']].map(([key,label])=><label key={key} style={{display:'block'}}>{label}<input aria-label={label} value={documentDraft[key] || ''} type={key.endsWith('Date')?'date':'text'} onChange={e=>editDocument(key,e.target.value)}/></label>)}
      {documentDraft.lines.map((line,index)=><fieldset key={index}><legend>Строка {index+1}</legend>
        {[['materialName','Материал'],['unit','Единица'],['quantity','Количество по документу']].map(([key,label])=><label key={key} style={{display:'block'}}>{label}<input aria-label={`${label} ${index+1}`} type={key==='quantity'?'number':'text'} step="any" value={line[key] ?? ''} onChange={e=>editLine(index,key,e.target.value)}/></label>)}
        <button type="button" onClick={()=>editDocument('lines',documentDraft.lines.filter((_,i)=>i!==index))}>Удалить строку {index+1}</button>
      </fieldset>)}
      <button type="button" onClick={()=>editDocument('lines',[...documentDraft.lines,{materialName:'',unit:'',quantity:''}])}>Добавить строку</button>
      <button type="button" disabled={!payload.originalUrls.length} onClick={()=>{generation.current++;setResult(null);setPayload({...initialPayload,document:documentDraft});}}>Повторить проверку</button>
    </details>}
    {paymentDocument && <p>Счёт на оплату не подтверждает поставку. Для приёмки потребуется отдельно загрузить фактическую накладную или УПД.</p>}
    {error && <p role="alert">{error}</p>}
    {!result && !error && <p role="status">Сверяем документ с отгрузками…</p>}
    {complete ? <p role="status">Приёмка подтверждена. Повторное оприходование заблокировано.</p> : result?.status === 'existing_receipt' ? <>
      <p>Документ уже оприходован. Повторное создание прихода заблокировано.</p>
      {(result.receipts || []).map(receipt => <section key={receipt.id}>
        <p>Накладная № {receipt.number} от {receipt.date} · {receipt.project || 'Основной склад'}</p>
        {(receipt.lines || []).map((line, index) => <p key={index}>{line.materialName}: {line.quantity} {line.unit}</p>)}
        {onOpenReceipt && <button type="button" onClick={() => onOpenReceipt(receipt.id)}>Открыть существующий приход #{receipt.id}</button>}
      </section>)}
    </> : result?.status === 'match' && !paymentDocument ? <>
      <p>Накладная № {result.matchedBatch?.waybillNumber} от {result.matchedBatch?.waybillDate || payload.document.waybillDate}. Проверьте каждую строку.</p>
      <p>Поставщик: {result.matchedBatch?.documentParties?.supplier?.fullName || payload.document.supplierInn}. Покупатель: {result.matchedBatch?.documentParties?.buyer?.fullName || payload.document.buyerInn}.</p>
      <p>Место приёмки: {matchedLocation}{result.matchedBatch?.documentParties?.consignee?.deliveryAddress ? ` · ${result.matchedBatch.documentParties.consignee.deliveryAddress}` : ''}</p>
      {matchedLocation !== (payload.project || 'Основной склад') && <p role="alert">Отгрузка относится к объекту «{matchedLocation}». {destinationMismatch ? 'Выбран другой объект, приёмка заблокирована.' : 'Приход будет оформлен на склад этого объекта. Проверьте место фактической поставки.'}</p>}
      {lines.map(line => <fieldset key={line.id} style={{marginBottom:12}}>
        <legend>{line.materialName} · {line.unit}</legend>
        {line.invoiceProgress && <p>По счёту #{line.invoiceProgress.sourceInvoiceId}: всего {line.invoiceProgress.orderedQuantity}, принято {line.invoiceProgress.acceptedQuantity}, осталось {line.invoiceProgress.remainingQuantity} {line.unit}.</p>}
        <p>Отгружено: {line.shippedQuantity}. {accepted(line) ? `Принято: ${line.receivedQuantity ?? 'не указано'}. Недостача: ${line.receivedQuantity == null ? 'не указана' : Math.max(0, Number(line.shippedQuantity) - Number(line.receivedQuantity))}. Строка закрыта.` : `Ожидает приёмки: ${line.shippedQuantity}.`}</p>
        {accepted(line) ? <>{Array.isArray(line.receiptOriginalUrls) && line.receiptOriginalUrls.map((url,index)=><SupplyFileLink key={url} url={url} fileSrc={value=>API+value}>Оригинал принятой поставки {index+1}</SupplyFileLink>)}{line.warehouseInvoiceId && <p>Приходная накладная #{line.warehouseInvoiceId} {onOpenReceipt && <button type="button" onClick={() => onOpenReceipt(line.warehouseInvoiceId)}>Открыть приход</button>}</p>}</> : <>
          <label>Фактически принято: {line.materialName}<input type="number" min="0" max={line.shippedQuantity} step="any" value={actual[line.id]?.receivedQuantity ?? ''} onChange={e => change(line.id, 'receivedQuantity', e.target.value)} disabled={busy}/></label>
          <label>Качество: {line.materialName}<select value={actual[line.id]?.qualityStatus || 'Принято'} onChange={e => change(line.id, 'qualityStatus', e.target.value)} disabled={busy}>{['Принято','Частично','Недостача','Брак','Несоответствие'].map(value => <option key={value}>{value}</option>)}</select></label>
          <label>Примечания: {line.materialName}<textarea value={actual[line.id]?.qualityNotes || ''} onChange={e => change(line.id, 'qualityNotes', e.target.value)} disabled={busy}/></label>
          <label>Претензия: {line.materialName}<textarea value={actual[line.id]?.claimDescription || ''} onChange={e => change(line.id, 'claimDescription', e.target.value)} disabled={busy}/></label>
        </>}
      </fieldset>)}
      {remaining.length ? <><p>Недостача окончательна для этой отгрузки. Допоставка оформляется новой отгрузкой.</p><label><input type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)}/>Подтверждаю: поставка физически прибыла, количество и состояние проверены.</label><button type="button" disabled={!confirmed || !valid || busy || destinationMismatch || documentDraft !== payload.document} onClick={submit}>Подтвердить фактическую приёмку</button></> : <p>Эта поставка уже принята. Повторная приёмка недоступна.</p>}
    </> : (result?.status === 'ambiguous' || sourceChoice) && candidates.length > 0 ? <>
      <p>{sourceChoice ? 'Выберите отгрузку по счёту. Затем загрузите фактическую накладную или УПД этой поставки.' : 'Найдены несколько отгрузок. Выберите нужную и подтвердите связь с оригиналом документа.'}</p>
      <fieldset><legend>{sourceChoice ? 'Отгрузки по счёту' : 'Подходящие отгрузки'}</legend>
        {candidates.map(candidate => <label key={candidate.id} style={{display:'block',marginBottom:12}}>
          <input type="radio" name="receipt-candidate" value={candidate.id} checked={selectedCandidate === String(candidate.id)} disabled={documentChanged || busy} onChange={()=>{setSelectedCandidate(String(candidate.id));setSelectionConfirmed(false);}}/>
          Отгрузка #{candidate.id} · Накладная № {candidate.waybillNumber || 'не указан'} от {candidate.waybillDate || 'не указана'}
          {candidate.sourceSupplierInvoiceId && <span> · Счёт {candidate.sourceInvoice?.invoiceNumber || `#${candidate.sourceSupplierInvoiceId}`}{candidate.sourceInvoice?.invoiceDate ? ` от ${candidate.sourceInvoice.invoiceDate}` : ''}</span>}
          <span style={{display:'block'}}>Поставщик: {candidate.documentParties?.supplier?.fullName || candidate.documentParties?.supplier?.inn || 'не указан'}. Покупатель: {candidate.documentParties?.buyer?.fullName || candidate.documentParties?.buyer?.inn || 'не указан'}. Объект: {candidate.project || 'Основной склад'}.</span>
          {(candidate.lines || []).map((line,index)=><span key={line.id || index} style={{display:'block'}}>{line.materialName}: {line.shippedQuantity} {line.unit}{accepted(line) ? ' · уже принято' : ''}</span>)}
        </label>)}
      </fieldset>
      <label><input type="checkbox" checked={selectionConfirmed} disabled={!chosenCandidate || documentChanged || busy} onChange={e=>setSelectionConfirmed(e.target.checked)}/>Подтверждаю выбранную отгрузку и связь с загруженным документом.</label>
      <button type="button" disabled={!canChoose} onClick={chooseCandidate}>{sourceChoice ? 'Загрузить фактическую накладную' : 'Проверить выбранную отгрузку'}</button>
    </> : result?.status === 'no_match' && !paymentDocument && !payload.sourceSupplierInvoiceId && !payload.selectedBatchId ? <><p>Связанная отгрузка не найдена. Проверьте реквизиты и оригинал перед созданием отдельного документа.</p><button type="button" disabled={documentDraft !== payload.document} onClick={() => onNewDocument?.({ newDocumentConfirmed: true, physicalReceiptConfirmed: false, originalUrls: payload.originalUrls, receiptDocument: payload.document })}>Оформить отдельный документ</button></> : result && <p role="alert">Требуется проверка: {result.reason || result.message || 'данных недостаточно или найдены несколько отгрузок'}. Приёмка заблокирована, оригиналы сохранены. Проверьте реквизиты или загрузите другой документ.</p>}
    {onDifferentDocument && <button type="button" disabled={busy} onClick={onDifferentDocument}>Другой документ (сбросить черновик)</button>}
    <button type="button" disabled={busy} onClick={onCancel}>Закрыть</button>
  </section>;
}
