import React from 'react';
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
  newInvoice,
  setNewInvoice,
  projects = [],
}) {
  const galleryInputRef = React.useRef(null);
  const cameraInputRef = React.useRef(null);
  if (!showScanInvoice) return null;
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

  const uploadInvoicePhoto = async (file, location) => {
    const fd = new FormData();
    fd.append('file', file);
    const projectName = location && location !== 'Основной склад' ? location : 'Основной склад';
    fd.append('projectName', projectName);
    fd.append('context', 'warehouse-invoices');
    try {
      const resp = await fetch(API + '/upload-photo', {method:'POST', body:fd});
      const data = await resp.json().catch(() => ({}));
      return data.url || '';
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
    setScanningInvoice(true);
    const location = targetLocation;
    const warehouseTarget = getWarehouseTarget(location);
    const project = warehouseTarget === 'object' ? location : '';
    const selectedAction = 'receive_to_warehouse';
    const sourceType = warehouseTarget === 'object' ? 'scan_project_invoice' : 'scan_main_invoice';
    try {
      const normalizedPages = await normalizeInvoiceImageFiles(files, { maxSide: 2400, quality: 0.9 });
      const images = normalizedPages.map(page => ({
        data: page.base64,
        mimeType: page.mimeType,
        name: page.originalName,
      }));
      const resp = await fetch(API+'/scan-invoice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({images, target:'warehouse', location, project, warehouseTarget, selectedAction, sourceType})});
      const data = await resp.json();
      if(!data.ok) throw new Error(scanErrorMessage(data.error||'Ошибка'));
      const parsed = data.data;
      const parsedNumber = firstText(parsed.number, parsed.invoiceNumber, parsed.invoice_number, parsed.documentNumber, parsed.document_number, parsed.no);
      const parsedDate = firstText(parsed.date, parsed.invoiceDate, parsed.invoice_date, parsed.documentDate, parsed.document_date);
      const parsedSupplier = firstText(
        parsed.supplier,
        parsed.supplierName,
        parsed.supplier_name,
        parsed.seller,
        parsed.shipper,
        parsed.consignor,
        parsed.sender
      );
      const uploadedPhotos = (await Promise.all(normalizedPages.map(page => uploadInvoicePhoto(page.uploadFile, location)))).filter(Boolean);
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
      const numberFromScan = parsedNumber || buildScanDraftNumber();
      const normalizedDate = normalizeDate(parsedDate);
      const warnings = [];
      if (!parsedNumber) warnings.push('Номер документа не распознан: поставлен черновой номер, проверьте перед оплатой.');
      if (!parsedDate) warnings.push('Дата документа не распознана: поставлена сегодняшняя дата, проверьте перед сохранением.');
      if (!parsedSupplier) warnings.push('Поставщик не распознан: укажите его вручную, чтобы бухгалтерия связала первичку.');
      if (!normalizedItems.length) warnings.push('Строки товаров не распознаны: документ можно сохранить только после ручного добавления позиций.');
      if (uploadedPhotos.length < normalizedPages.length) warnings.push('Не все фото документа прикрепились: загружено ' + uploadedPhotos.length + ' из ' + normalizedPages.length + '. Повторите загрузку фото в карточке накладной перед оплатой.');
      if (!totalWithVat && !totalBase && itemsTotal > 0) warnings.push('Итог документа не распознан: сумма рассчитана по строкам, проверьте НДС и итог перед сохранением.');
      if (!totalWithVat && !totalBase && !itemsTotal) warnings.push('Сумма документа не распознана: заполните цены и итог вручную перед сохранением.');
      if (totalWithVat > 0 && itemsTotal > 0 && Math.abs(totalWithVat - itemsTotal) > Math.max(1, totalWithVat * 0.015)) {
        warnings.push('Сумма строк отличается от итога документа: проверьте количество, цену и НДС.');
      }
      setNewInvoice(prev=>{
        const photos = uploadedPhotos.length ? [...(prev.photos || []), ...uploadedPhotos] : (prev.photos || []);
        return {
          ...prev,
          location,
          project,
          warehouseTarget,
          selectedAction,
          sourceType,
          number:numberFromScan || prev.number || '',
          supplier:parsedSupplier,
          newSupplierName:parsedSupplier,
          isNewSupplier:Boolean(parsedSupplier) || prev.isNewSupplier,
          date:normalizedDate || today,
          acceptedBy:user?.name || '',
          vat:detectedVat,
          totalBase,
          totalVat,
          totalWithVat,
          pagesCount: parsed.pagesCount || photos.length || files.length,
          photos,
          photoUrls: photos,
          items:normalizedItems.length ? normalizedItems : prev.items,
          scanWarnings:warnings,
          scanDocumentType:parsed.documentType || parsed.document_type || '',
          scanDocumentTitle:parsed.documentTitle || parsed.document_title || '',
          scanConfidence:parsed.confidence ?? ''
        };
      });
      setShowScanInvoice(false);
      setShowScannedInvoiceForm(true);
      alert(files.length > 1 ? `Документ распознан: ${files.length} стр. Проверьте данные.` : 'Документ распознан! Проверьте данные.');
    } catch(e){
      alert(scanErrorMessage(e?.message));
    }
    setScanningInvoice(false);
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
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:isMobile?'16px':'20px',width:isMobile?'calc(100vw - 24px)':'340px',margin:isMobile?'12px':'20px',maxHeight:isMobile?'calc(100dvh - 24px)':'90vh',overflowY:'auto',boxSizing:'border-box'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>📷 Сканировать накладную / счёт</b>
        <label style={{display:'block',color:C.textSec,fontSize:'12px',fontWeight:700,marginBottom:'6px'}}>Куда принять</label>
        <select value={targetLocation} onChange={e=>updateLocation(e.target.value)} style={{width:'100%',boxSizing:'border-box',marginBottom:'12px',padding:'12px 14px',borderRadius:'12px',border:'1.5px solid '+C.border,backgroundColor:C.bg,color:C.text,fontSize:'14px'}}>
          <option value=''>Выберите склад или объект *</option>
          <option value='Основной склад'>📦 Основной склад</option>
          {projects.map(p=><option key={p.id || p.name} value={p.name}>🏗️ {p.name}</option>)}
        </select>
        <div style={{display:'block',marginBottom:'12px'}}>
          <input ref={galleryInputRef} type='file' accept={invoiceImageAccept} multiple style={{display:'none'}} onChange={onFilesPicked}/>
          <input ref={cameraInputRef} type='file' accept='image/*' multiple capture='environment' style={{display:'none'}} onChange={onFilesPicked}/>
          <div onClick={()=>openPicker(galleryInputRef)} role='button' tabIndex={0} onKeyDown={event=>{ if(event.key==='Enter' || event.key===' ') openPicker(galleryInputRef); }} style={{border:'2px dashed '+C.border,borderRadius:'12px',padding:isMobile?'22px':'30px',textAlign:'center',cursor:'pointer'}}>
            {scanningInvoice?<div><div style={{fontSize:'32px',marginBottom:'8px'}}>⏳</div><p style={{color:C.textSec,fontSize:'13px'}}>ИИ распознаёт страницы документа...</p></div>:<div><div style={{fontSize:'48px',marginBottom:'8px'}}>📷</div><p style={{color:C.text,fontSize:'14px',fontWeight:'600'}}>Выберите фото накладной или счёта</p><p style={{color:C.textSec,fontSize:'12px',marginTop:'4px'}}>Можно выбрать 1-8 страниц, ИИ соберёт их в один документ</p></div>}
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginTop:'8px'}}>
            <button type='button' disabled={scanningInvoice} onClick={()=>openPicker(galleryInputRef)} style={{...btnG,justifyContent:'center',opacity:scanningInvoice?0.6:1}}>🖼️ Галерея</button>
            <button type='button' disabled={scanningInvoice} onClick={()=>openPicker(cameraInputRef)} style={{...btnG,justifyContent:'center',opacity:scanningInvoice?0.6:1}}>📷 Камера</button>
          </div>
        </div>
        <button onClick={()=>setShowScanInvoice(false)} style={{...btnG,width:'100%',justifyContent:'center'}}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}
