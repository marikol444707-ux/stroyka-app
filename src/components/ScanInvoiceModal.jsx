import React from 'react';
import UnifiedReceiptReview from './UnifiedReceiptReview';
import { X } from 'lucide-react';
import { invoiceImageAccept, normalizeInvoiceImageFiles } from '../utils/invoiceImages';

export default function ScanInvoiceModal({
  showScanInvoice,
  setShowScanInvoice,
  setShowScannedInvoiceForm,
  C,
  card,
  btnG,
  scanningInvoice,
  setScanningInvoice,
  API,
  user,
  companyId,
  newInvoice,
  setNewInvoice,
  projects = [],
  unifiedReceipt = false,
  onDocumentScanned,
  onReceiptConfirmed,
  onOpenReceipt,
  onStandaloneReceipt,
}) {
  const galleryInputRef = React.useRef(null);
  const cameraInputRef = React.useRef(null);
  const [review, setReview] = React.useState(null);
  const [scanError, setScanError] = React.useState('');
  const sequence = React.useRef(0);
  const effectiveCompanyId = companyId ?? user?.companyId ?? user?.company_id;
  const activeScope = `${effectiveCompanyId ?? ''}:${newInvoice?.location || ''}:${newInvoice?.receiptDraftId || ''}:${newInvoice?.sourceSupplierInvoiceId || ''}:${newInvoice?.selectedBatchId || ''}`;
  const sourceScope = `${effectiveCompanyId ?? ''}:${newInvoice?.location || ''}`;
  const scopeRef = React.useRef(activeScope);
  scopeRef.current = activeScope;
  React.useEffect(() => { const token = sequence; token.current++; return () => { token.current++; }; }, [showScanInvoice]);
  React.useEffect(() => { sequence.current++; setReview(null); setScanError(''); setScanningInvoice(false); }, [activeScope, setScanningInvoice]);
  React.useEffect(() => {
    if (newInvoice?.receiptSourceScope && newInvoice.receiptSourceScope !== sourceScope) {
      setNewInvoice(prev => ({location:prev.location, project:prev.project, items:[], photos:[], photoUrls:[], originalUrls:[], receiptDraftId:`${Date.now()}-${Math.random()}`}));
    }
  }, [newInvoice?.receiptSourceScope, sourceScope, setNewInvoice]);
  const close = () => { sequence.current++; setScanningInvoice(false); setShowScanInvoice(false); };
  const resetDocument = (source = {}) => {
    sequence.current++;
    setReview(null); setScanError(''); setScanningInvoice(false);
    setNewInvoice({location:newInvoice.location, project:newInvoice.project, items:[], photos:[], photoUrls:[], originalUrls:[], receiptDraftId:`${Date.now()}-${Math.random()}`, ...source});
  };
  if (!showScanInvoice && !review) return null;
  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 640;

  const toNumber = (value) => {
    if (value === null || value === undefined || value === '') return 0;
    if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
    const normalized = String(value)
      .replace(/\s+/g, '')
      .replace(/[₽руб.]/gi, '')
      .replace(',', '.')
      .replace(/[^\d.-]/g, '');
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const normalizeDate = (value) => {
    const text = String(value || '').trim();
    if (!text) return '';
    const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
    const ru = text.match(/(\d{1,2})[.\-/\s]+(\d{1,2})[.\-/\s]+(\d{2,4})/);
    if (!ru) return '';
    const year = ru[3].length === 2 ? `20${ru[3]}` : ru[3];
    return `${year}-${ru[2].padStart(2, '0')}-${ru[1].padStart(2, '0')}`;
  };

  const detectVat = (parsed = {}) => {
    const rawVat = String(parsed.vat || parsed.tax || parsed.vatType || '').toLowerCase();
    const rate = toNumber(parsed.vatRate ?? parsed.vat_rate ?? parsed.vatPercent ?? parsed.vat_percent);
    const vatAmount = toNumber(parsed.totalVat ?? parsed.total_vat ?? parsed.vatAmount ?? parsed.vat_amount);
    const totalWithVat = toNumber(parsed.totalWithVat ?? parsed.total_with_vat ?? parsed.grandTotal ?? parsed.grand_total ?? parsed.total ?? parsed.amount);
    const totalBase = toNumber(parsed.totalBase ?? parsed.total_base ?? parsed.totalWithoutVat ?? parsed.total_without_vat);
    const inferredVat = totalWithVat > 0 && totalBase > 0 ? Math.max(0, totalWithVat - totalBase) : 0;
    const inferredRate = totalBase > 0 && inferredVat > 0 ? inferredVat / totalBase * 100 : 0;
    const hasVat = parsed.vatIncluded === true || parsed.hasVat === true || vatAmount > 0 || rate > 0 || /ндс/.test(rawVat);
    if ((!hasVat && inferredVat <= 0) || /без\s*ндс/.test(rawVat)) return 'Без НДС';
    if (Math.abs(rate - 20) < 0.5 || Math.abs(inferredRate - 20) < 0.75 || /20\s*%/.test(rawVat)) return 'С НДС 20%';
    return 'С НДС 22%';
  };

  const firstText = (...values) => {
    for (const value of values) {
      const text = String(value || '').trim();
      if (text) return text;
    }
    return '';
  };

  const buildScanDraftNumber = () => {
    const d = new Date();
    const stamp = [
      d.getFullYear(),
      String(d.getMonth() + 1).padStart(2, '0'),
      String(d.getDate()).padStart(2, '0'),
    ].join('');
    const time = [
      String(d.getHours()).padStart(2, '0'),
      String(d.getMinutes()).padStart(2, '0'),
    ].join('');
    return `SCAN-${stamp}-${time}`;
  };

  const targetLocation = newInvoice?.location || '';
  const getWarehouseTarget = (location) => location && location !== 'Основной склад' ? 'object' : 'main';
  const updateLocation = (location) => {
    const warehouseTarget = getWarehouseTarget(location);
    setNewInvoice(prev => ({
      ...prev,
      location,
      project: warehouseTarget === 'object' ? location : '',
      warehouseTarget,
      selectedAction: 'receive_to_warehouse',
      sourceType: warehouseTarget === 'object' ? 'scan_project_invoice' : 'scan_main_invoice',
    }));
  };

  const uploadInvoicePhoto = async (file, location, projectId) => {
    const fd = new FormData();
    fd.append('file', file);
    const projectName = location && location !== 'Основной склад' ? location : 'Основной склад';
    fd.append('projectName', projectName);
    if (projectId) fd.append('projectId', String(projectId));
    fd.append('context', 'warehouse-invoices');
    try {
      const resp = await fetch(API + '/upload-photo', {method:'POST', body:fd});
      const data = await resp.json().catch(() => ({}));
      return resp.ok ? (data.url || '') : '';
    } catch (_e) {
      return '';
    }
  };

  const scanErrorMessage = (message) => {
    const text = String(message || '').trim();
    if (/unterminated|string starting|json|line \d+|column \d+|char \d+/i.test(text)) {
      return 'ИИ не смог корректно разобрать документ. Проверьте, что видна таблица товаров, номер, дата и поставщик.';
    }
    return text || 'Не удалось распознать. Попробуйте ещё раз.';
  };

  const scan = async (fileList) => {
    const files = Array.from(fileList || []).filter(Boolean).slice(0, 8);
    if(!files.length) return;
    if (!targetLocation) {
      alert('Сначала выберите, куда принять документ: основной склад или объект.');
      return;
    }
    if (scanningInvoice) return;
    let projectId;
    if (getWarehouseTarget(targetLocation) === 'object') {
      const matches = projects.filter(project => {
        const owner = project.companyId ?? project.company_id;
        return project.name === targetLocation
          && (owner == null || effectiveCompanyId == null || String(owner) === String(effectiveCompanyId));
      });
      const id = Number(matches[0]?.id);
      if (matches.length !== 1 || !Number.isSafeInteger(id) || id <= 0) {
        setScanError('Не удалось однозначно определить объект в выбранной компании. Обновите список объектов и выберите объект снова. Оригиналы не загружены.');
        return;
      }
      projectId = id;
    }
    if (newInvoice.requiresWaybill && newInvoice.receiptSourceProjectId != null && String(projectId) !== String(newInvoice.receiptSourceProjectId)) {
      setScanError('Объект выбранной отгрузки изменился. Сбросьте черновик и выберите счёт снова. Оригиналы не загружены.');
      return;
    }
    const request = ++sequence.current;
    const scope = activeScope;
    const current = () => request === sequence.current && scope === scopeRef.current;
    const initialDraft = newInvoice;
    setScanError('');
    setScanningInvoice(true);
    const location = targetLocation;
    const warehouseTarget = getWarehouseTarget(location);
    const project = warehouseTarget === 'object' ? location : '';
    const selectedAction = 'receive_to_warehouse';
    const sourceType = warehouseTarget === 'object' ? 'scan_project_invoice' : 'scan_main_invoice';
    let uploadedPhotos = [];
    try {
      // Preserve original files before recognition, including PDFs and failed OCR.
      for (const file of files) {
        const url = await uploadInvoicePhoto(file, location, projectId);
        if (!current()) return;
        if (!url) throw new Error('Не удалось сохранить все оригиналы. Приёмка заблокирована. Повторите загрузку.');
        uploadedPhotos.push(url);
        setNewInvoice(prev => ({...prev, photos:[...(prev.photos || []), url], photoUrls:[...(prev.photoUrls || []), url], originalUrls:[...(prev.originalUrls || []), url]}));
      }
      const normalizedPages = await normalizeInvoiceImageFiles(files, { maxSide: 2400, quality: 0.9 });
      if (!current()) return;
      const images = normalizedPages.map(page => ({
        data: page.base64,
        mimeType: page.mimeType,
        name: page.originalName,
      }));
      const resp = await fetch(API+'/scan-invoice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({images, target:'warehouse', location, project, warehouseTarget, selectedAction, sourceType})});
      const data = await resp.json();
      if (!current()) return;
      if(!resp.ok || !data.ok) throw new Error(scanErrorMessage(data.error||'Ошибка'));
      const parsed = data.data;
      const scanRecognition = parsed.recognition || parsed.scanRecognition || null;
      const parsedNumber = firstText(parsed.number, parsed.invoiceNumber, parsed.invoice_number, parsed.documentNumber, parsed.document_number, parsed.no);
      const parsedDate = firstText(parsed.date, parsed.invoiceDate, parsed.invoice_date, parsed.documentDate, parsed.document_date);
      const parsedSupplier = firstText(
        parsed.supplier,
        parsed.supplierName,
        parsed.supplier_name,
        parsed.seller,
        parsed.shipper,
        parsed.consignor,
        parsed.sender,
        scanRecognition?.supplierName
      );

      const today = new Date().toISOString().split('T')[0];
      const totalWithVatRaw = toNumber(parsed.totalWithVat ?? parsed.total_with_vat ?? parsed.grandTotal ?? parsed.grand_total ?? parsed.total ?? parsed.amount);
      const totalBaseRaw = toNumber(parsed.totalBase ?? parsed.total_base ?? parsed.totalWithoutVat ?? parsed.total_without_vat);
      const totalVatRaw = toNumber(parsed.totalVat ?? parsed.total_vat ?? parsed.vatAmount ?? parsed.vat_amount);
      const normalizedItems = (parsed.items || []).map(item => {
        const quantity = toNumber(item.quantity);
        const lineTotal = toNumber(item.lineTotalWithVat ?? item.line_total_with_vat ?? item.lineTotal ?? item.line_total ?? item.total);
        const rawPrice = toNumber(item.priceWithVat ?? item.price_with_vat ?? item.price ?? item.unitPrice ?? item.unit_price);
        const price = rawPrice > 0 ? rawPrice : (quantity > 0 && lineTotal > 0 ? lineTotal / quantity : 0);
        return {
          name:item.name||'',
          quantity:String(quantity),
          unit:item.unit||'шт',
          price:String(price),
          lineTotal:String(lineTotal || quantity * price),
          category:'',
          workPackage:''
        };
      });
      const itemsTotal = normalizedItems.reduce((sum, item) => sum + toNumber(item.lineTotal), 0);
      const detectedVat = detectVat(parsed);
      const vatRate = detectedVat.includes('22') ? 22 : detectedVat.includes('20') ? 20 : 0;
      let totalWithVat = totalWithVatRaw || (totalBaseRaw && totalVatRaw ? totalBaseRaw + totalVatRaw : itemsTotal);
      let totalVat = totalVatRaw;
      let totalBase = totalBaseRaw;
      if (detectedVat === 'Без НДС') {
        totalVat = 0;
        if (!totalBase && totalWithVat) totalBase = totalWithVat;
      } else if (!totalVat && totalWithVat && totalBase) {
        totalVat = Math.max(0, totalWithVat - totalBase);
      } else if (!totalBase && totalWithVat && totalVat) {
        totalBase = Math.max(0, totalWithVat - totalVat);
      } else if (!totalBase && !totalVat && totalWithVat && vatRate) {
        totalBase = totalWithVat / (1 + vatRate / 100);
        totalVat = totalWithVat - totalBase;
      } else if (!totalWithVat && totalBase && totalVat) {
        totalWithVat = totalBase + totalVat;
      }
      totalWithVat = Math.round((totalWithVat || 0) * 100) / 100;
      totalBase = Math.round((totalBase || 0) * 100) / 100;
      totalVat = Math.round((totalVat || 0) * 100) / 100;
      const numberFromScan = parsedNumber || (unifiedReceipt ? '' : buildScanDraftNumber());
      const normalizedDate = normalizeDate(parsedDate);
      const warnings = [];
      if (!parsedNumber) warnings.push(unifiedReceipt ? 'Номер документа не распознан: перенесите номер из оригинала.' : 'Номер документа не распознан: поставлен черновой номер, проверьте перед оплатой.');
      if (!parsedDate) warnings.push(unifiedReceipt ? 'Дата документа не распознана: перенесите дату из оригинала.' : 'Дата документа не распознана: поставлена сегодняшняя дата, проверьте перед сохранением.');
      if (!parsedSupplier) warnings.push('Поставщик не распознан: укажите его вручную, чтобы бухгалтерия связала первичку.');
      if (!normalizedItems.length) warnings.push('Строки товаров не распознаны: документ можно сохранить только после ручного добавления позиций.');
      if (uploadedPhotos.length < normalizedPages.length) warnings.push('Не все фото документа прикрепились: загружено ' + uploadedPhotos.length + ' из ' + normalizedPages.length + '. Повторите загрузку фото в карточке накладной перед оплатой.');
      if (!totalWithVat && !totalBase && itemsTotal > 0) warnings.push('Итог документа не распознан: сумма рассчитана по строкам, проверьте НДС и итог перед сохранением.');
      if (!totalWithVat && !totalBase && !itemsTotal) warnings.push('Сумма документа не распознана: заполните цены и итог вручную перед сохранением.');
      if (totalWithVat > 0 && itemsTotal > 0 && Math.abs(totalWithVat - itemsTotal) > Math.max(1, totalWithVat * 0.015)) {
        warnings.push('Сумма строк отличается от итога документа: проверьте количество, цену и НДС.');
      }
      setNewInvoice(prev=>{
        const photos = prev.photos || uploadedPhotos;
        const draft = {
          ...prev,
          location,
          project,
          warehouseTarget,
          selectedAction,
          sourceType,
          number:unifiedReceipt ? numberFromScan : numberFromScan || prev.number || '',
          supplier:parsedSupplier,
          newSupplierName:parsedSupplier,
          supplierInn:firstText(parsed.supplierInn, parsed.supplier_inn, parsed.inn),
          supplierKpp:firstText(parsed.supplierKpp, parsed.supplier_kpp, parsed.kpp),
          supplierOgrn:firstText(parsed.supplierOgrn, parsed.supplier_ogrn, parsed.ogrn),
          isNewSupplier:Boolean(parsedSupplier) || prev.isNewSupplier,
          date:normalizedDate || (unifiedReceipt ? '' : today),
          acceptedBy:user?.name || '',
          vat:detectedVat,
          totalBase,
          totalVat,
          totalWithVat,
          pagesCount: parsed.pagesCount || photos.length || files.length,
          photos,
          photoUrls: photos,
          originalUrls: uploadedPhotos,
          items:normalizedItems.length ? normalizedItems : prev.items,
          scanWarnings:warnings,
          scanDocumentType:parsed.documentType || parsed.document_type || '',
          scanDocumentTitle:parsed.documentTitle || parsed.document_title || '',
          scanConfidence:parsed.confidence ?? scanRecognition?.confidence ?? '',
          scanRecognition,
          scanHasManualCorrections:false
        };
        // Never replace fields edited while upload/recognition was pending.
        Object.keys(draft).forEach(key => {
          if (!['photos', 'photoUrls', 'originalUrls'].includes(key) && prev[key] !== initialDraft?.[key]) draft[key] = prev[key];
        });
        return draft;
      });
      const scanResult = {parsed, originalUrls:uploadedPhotos, location, project, projectId, companyId:effectiveCompanyId, sourceSupplierInvoiceId:initialDraft.sourceSupplierInvoiceId, selectedBatchId:initialDraft.selectedBatchId, explicitSelectionConfirmed:initialDraft.explicitSelectionConfirmed};
      if (onDocumentScanned) { await onDocumentScanned(scanResult); return; }
      if (unifiedReceipt) { setReview(scanResult); return; }
      setShowScanInvoice(false);
      setShowScannedInvoiceForm(true);
	      const hasPdf = normalizedPages.some(page => page.isPdf);
	      alert(hasPdf ? 'PDF распознан! Проверьте данные.' : (files.length > 1 ? `Документ распознан: ${files.length} стр. Проверьте данные.` : 'Документ распознан! Проверьте данные.'));
    } catch(e){
      if (current()) {
        setScanError(scanErrorMessage(e?.message) + (uploadedPhotos.length ? ' Оригиналы сохранены в черновике. Требуется ручная проверка; приёмка не выполнена.' : ''));
        if (unifiedReceipt && uploadedPhotos.length === files.length) setReview({parsed:{},originalUrls:uploadedPhotos,location,project,projectId,companyId:effectiveCompanyId,sourceSupplierInvoiceId:initialDraft.sourceSupplierInvoiceId,selectedBatchId:initialDraft.selectedBatchId,explicitSelectionConfirmed:initialDraft.explicitSelectionConfirmed,recognitionError:scanErrorMessage(e?.message)});
      }
    } finally { if (current()) setScanningInvoice(false); }
  };

  const onFilesPicked = async (event) => {
    await scan(event.target.files);
    event.target.value = '';
  };

  const openPicker = (ref) => {
    if (scanningInvoice) return;
    ref.current?.click();
  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:showScanInvoice?'flex':'none',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:isMobile?'16px':'20px',width:isMobile?'calc(100vw - 24px)':review?'700px':'340px',margin:isMobile?'12px':'20px',maxHeight:isMobile?'calc(100dvh - 24px)':'90vh',overflowY:'auto',boxSizing:'border-box'}}>
        {review ? <UnifiedReceiptReview API={API} scan={review} onDifferentDocument={() => resetDocument()} onWaybillRequired={source => resetDocument({...source, requiresWaybill:true, receiptSourceScope:sourceScope, receiptSourceProjectId:review.projectId})} onConfirmed={result => { setNewInvoice(prev => ({...prev,receiptCompleted:true})); onReceiptConfirmed?.(result); }} onOpenReceipt={onOpenReceipt} onCancel={close} onNewDocument={confirmation => {
          const document = confirmation.receiptDocument;
          const draft = {...newInvoice, ...confirmation, ...(document ? {
            number:document.waybillNumber, date:document.waybillDate,
            supplierInn:document.supplierInn, buyerInn:document.buyerInn,
            scanDocumentType:document.documentType,
            items:document.lines.map((line,index) => ({
              ...(newInvoice.items?.[index]?.name === line.materialName ? newInvoice.items[index] : {price:'',category:'',workPackage:''}),
              name:line.materialName,unit:line.unit,quantity:String(line.quantity),
            })),
          } : {})};
          setNewInvoice(draft);
          close();
          if (onStandaloneReceipt) onStandaloneReceipt(draft);
          else setShowScannedInvoiceForm?.(true);
        }}/> : <>
        {scanError && <p role='alert'>{scanError}</p>}
        {newInvoice.requiresWaybill && <p role='status'>Выбрана отгрузка #{newInvoice.selectedBatchId} по счёту #{newInvoice.sourceSupplierInvoiceId}. Загрузите фактическую накладную или УПД. Счёт сохранён отдельно и не используется как подтверждение поставки.</p>}
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>📷 Сканировать накладную / счёт</b>
        <label style={{display:'block',color:C.textSec,fontSize:'12px',fontWeight:700,marginBottom:'6px'}}>Куда принять</label>
        <select disabled={scanningInvoice || newInvoice.requiresWaybill} value={targetLocation} onChange={e=>updateLocation(e.target.value)} style={{width:'100%',boxSizing:'border-box',marginBottom:'12px',padding:'12px 14px',borderRadius:'12px',border:'1.5px solid '+C.border,backgroundColor:C.bg,color:C.text,fontSize:'14px'}}>
          <option value=''>Выберите склад или объект *</option>
          <option value='Основной склад'>📦 Основной склад</option>
          {projects.map(p=><option key={p.id || p.name} value={p.name}>🏗️ {p.name}</option>)}
        </select>
        <div style={{display:'block',marginBottom:'12px'}}>
          <input aria-label='Оригиналы документа' ref={galleryInputRef} type='file' accept={invoiceImageAccept} multiple style={{display:'none'}} onChange={onFilesPicked}/>
          <input ref={cameraInputRef} type='file' accept='image/*' multiple capture='environment' style={{display:'none'}} onChange={onFilesPicked}/>
          <div onClick={()=>openPicker(galleryInputRef)} role='button' tabIndex={0} onKeyDown={event=>{ if(event.key==='Enter' || event.key===' ') openPicker(galleryInputRef); }} style={{border:'2px dashed '+C.border,borderRadius:'12px',padding:isMobile?'22px':'30px',textAlign:'center',cursor:'pointer'}}>
	            {scanningInvoice?<div><div style={{fontSize:'32px',marginBottom:'8px'}}>⏳</div><p style={{color:C.textSec,fontSize:'13px'}}>ИИ распознаёт документ...</p></div>:<div><div style={{fontSize:'48px',marginBottom:'8px'}}>📄</div><p style={{color:C.text,fontSize:'14px',fontWeight:'600'}}>Выберите PDF или фото накладной/счёта</p><p style={{color:C.textSec,fontSize:'12px',marginTop:'4px'}}>Можно выбрать PDF или 1-8 фото страниц, ИИ соберёт их в один документ</p></div>}
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginTop:'8px'}}>
            <button type='button' disabled={scanningInvoice} onClick={()=>openPicker(galleryInputRef)} style={{...btnG,justifyContent:'center',opacity:scanningInvoice?0.6:1}}>🖼️ Галерея</button>
            <button type='button' disabled={scanningInvoice} onClick={()=>openPicker(cameraInputRef)} style={{...btnG,justifyContent:'center',opacity:scanningInvoice?0.6:1}}>📷 Камера</button>
          </div>
        </div>
        {newInvoice.requiresWaybill && <button type='button' disabled={scanningInvoice} onClick={() => resetDocument()}>Другой документ (сбросить черновик)</button>}
        <button onClick={close} style={{...btnG,width:'100%',justifyContent:'center'}}><X size={14}/>Отмена</button>
        </> }
      </div>
    </div>
  );
}
