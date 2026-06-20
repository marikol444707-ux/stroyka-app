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
    const hasVat = parsed.vatIncluded === true || parsed.hasVat === true || vatAmount > 0 || rate > 0 || /ндс/.test(rawVat);
    if (!hasVat || /без\s*ндс/.test(rawVat)) return 'Без НДС';
    if (Math.abs(rate - 20) < 0.5 || /20\s*%/.test(rawVat)) return 'С НДС 20%';
    return 'С НДС 22%';
  };

  const targetLocation = newInvoice?.location || 'Основной склад';
  const updateLocation = (location) => {
    setNewInvoice(prev => ({
      ...prev,
      location,
      project: location && location !== 'Основной склад' ? location : '',
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

  const scan = async (fileList) => {
    const files = Array.from(fileList || []).filter(Boolean).slice(0, 8);
    if(!files.length) return;
    setScanningInvoice(true);
    const location = targetLocation || 'Основной склад';
    const project = location !== 'Основной склад' ? location : '';
    try {
      const normalizedPages = await normalizeInvoiceImageFiles(files);
      const images = normalizedPages.map(page => ({
        data: page.base64,
        mimeType: page.mimeType,
        name: page.originalName,
      }));
      const resp = await fetch(API+'/scan-invoice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({images, target:'warehouse', location, project})});
      const data = await resp.json();
      if(!data.ok) throw new Error(data.error||'Ошибка');
      const parsed = data.data;
      const uploadedPhotos = (await Promise.all(normalizedPages.map(page => uploadInvoicePhoto(page.uploadFile, location)))).filter(Boolean);
      const today = new Date().toISOString().split('T')[0];
      const totalWithVat = toNumber(parsed.totalWithVat ?? parsed.total_with_vat ?? parsed.grandTotal ?? parsed.grand_total ?? parsed.total ?? parsed.amount);
      const totalBase = toNumber(parsed.totalBase ?? parsed.total_base ?? parsed.totalWithoutVat ?? parsed.total_without_vat);
      const totalVat = toNumber(parsed.totalVat ?? parsed.total_vat ?? parsed.vatAmount ?? parsed.vat_amount);
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
      setNewInvoice(prev=>({...prev,
        location,
        project,
        number:parsed.number || parsed.invoiceNumber || parsed.invoice_number || prev.number || '',
        supplier:parsed.supplier||'',
        newSupplierName:parsed.supplier||'',
        isNewSupplier:true,
        date:normalizeDate(parsed.date || parsed.invoiceDate || parsed.invoice_date) || today,
        acceptedBy:user?.name || '',
        vat:detectVat(parsed),
        totalBase,
        totalVat,
        totalWithVat,
        pagesCount: parsed.pagesCount || files.length,
        photos: uploadedPhotos.length ? [...(prev.photos || []), ...uploadedPhotos] : (prev.photos || []),
        items:normalizedItems.length ? normalizedItems : prev.items
      }));
      setShowScanInvoice(false);
      setShowScannedInvoiceForm(true);
      alert(files.length > 1 ? `Накладная распознана: ${files.length} стр. Проверьте данные.` : 'Накладная распознана! Проверьте данные.');
    } catch(e){
      alert(e?.message || 'Не удалось распознать. Попробуйте ещё раз.');
    }
    setScanningInvoice(false);
  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:isMobile?'16px':'20px',width:isMobile?'calc(100vw - 24px)':'340px',margin:isMobile?'12px':'20px',maxHeight:isMobile?'calc(100dvh - 24px)':'90vh',overflowY:'auto',boxSizing:'border-box'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>📷 Сканировать накладную</b>
        <label style={{display:'block',color:C.textSec,fontSize:'12px',fontWeight:700,marginBottom:'6px'}}>Куда принять</label>
        <select value={targetLocation} onChange={e=>updateLocation(e.target.value)} style={{width:'100%',boxSizing:'border-box',marginBottom:'12px',padding:'12px 14px',borderRadius:'12px',border:'1.5px solid '+C.border,backgroundColor:C.bg,color:C.text,fontSize:'14px'}}>
          <option value='Основной склад'>📦 Основной склад</option>
          {projects.map(p=><option key={p.id || p.name} value={p.name}>🏗️ {p.name}</option>)}
        </select>
        <label style={{display:'block',marginBottom:'12px',cursor:'pointer'}}>
          <input type='file' accept={invoiceImageAccept} multiple capture='environment' style={{display:'none'}} onChange={e=>scan(e.target.files)}/>
          <div style={{border:'2px dashed '+C.border,borderRadius:'12px',padding:'30px',textAlign:'center',cursor:'pointer'}}>
            {scanningInvoice?<div><div style={{fontSize:'32px',marginBottom:'8px'}}>⏳</div><p style={{color:C.textSec,fontSize:'13px'}}>ИИ распознаёт страницы накладной...</p></div>:<div><div style={{fontSize:'48px',marginBottom:'8px'}}>📷</div><p style={{color:C.text,fontSize:'14px',fontWeight:'600'}}>Выберите фото накладной</p><p style={{color:C.textSec,fontSize:'12px',marginTop:'4px'}}>Можно выбрать 1-8 страниц, ИИ соберёт их в одну накладную</p></div>}
          </div>
        </label>
        <button onClick={()=>setShowScanInvoice(false)} style={{...btnG,width:'100%',justifyContent:'center'}}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}
