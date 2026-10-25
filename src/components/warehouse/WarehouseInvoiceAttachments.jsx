import React from 'react';
import {invoiceImageAccept, normalizeInvoiceImageFiles} from '../../utils/invoiceImages';
import {readStoredCompanyRequestContext} from '../../features/company-context/companyContextStorage';

export default function WarehouseInvoiceAttachments({newInvoice,setNewInvoice,uploadPhoto,fileSrc=url=>url,setShowPhotoModal,C={},onBusy}) {
  const galleryRef=React.useRef(null);
  const cameraRef=React.useRef(null);
  const pendingRef=React.useRef(null);
  const invoiceRef=React.useRef(newInvoice);
  const mountedRef=React.useRef(true);
  const busyRef=React.useRef(false);
  const [uploading,setUploading]=React.useState(false);
  const [error,setError]=React.useState('');
  invoiceRef.current=newInvoice;
  React.useEffect(()=>{
    mountedRef.current=true;
    return ()=>{ mountedRef.current=false; pendingRef.current=null; };
  },[]);
  const scope=()=>JSON.stringify([invoiceRef.current.id,invoiceRef.current.location,readStoredCompanyRequestContext()]);

  const attach=async files=>{
    if (!files.length || busyRef.current) return;
    const owner=scope();
    const selection=readStoredCompanyRequestContext();
    if (selection?.mode==='all_companies') {
      setError('Выберите одну компанию перед загрузкой накладной.');
      return;
    }
    pendingRef.current={files,owner};
    busyRef.current=true;
    setUploading(true);
    onBusy?.(true);
    setError('');
    try {
      const pages=await normalizeInvoiceImageFiles(files);
      if (!mountedRef.current || scope()!==owner) return;
      const results=await Promise.allSettled(pages.map(page=>uploadPhoto(page.originalFile || page.uploadFile,{
        projectName:invoiceRef.current.location || 'Основной склад',context:'warehouse-invoices',
        ...(selection?.companyId ? {companyId:selection.companyId} : {}),
      })));
      if (!mountedRef.current || scope()!==owner) return;
      const urls=[];
      const failed=[];
      results.forEach((result,index)=>{
        if (result.status==='fulfilled' && typeof result.value==='string' && result.value.trim()) urls.push(result.value);
        else failed.push(files[index]);
      });
      if (urls.length) setNewInvoice(current=>{
        if (JSON.stringify([current.id,current.location,readStoredCompanyRequestContext()])!==owner) return current;
        const photos=[...new Set([...(current.photoUrls || []),...(current.photos || []),
          ...(current.photoUrl ? [current.photoUrl] : []),...urls])];
        return {...current,photos,photoUrls:photos,photoUrl:photos[0]};
      });
      pendingRef.current=failed.length ? {files:failed,owner} : null;
      if (failed.length) setError(urls.length
        ? `Добавлено файлов: ${urls.length}. Не удалось загрузить: ${failed.length}. Повторите загрузку оставшихся файлов.`
        : 'Сервер не принял фото или PDF. Повторите загрузку. Если ошибка повторится, проверьте доступ к выбранной компании и соединение.');
    } catch (failure) {
      if (mountedRef.current && scope()===owner) setError(failure?.message || 'Не удалось подготовить файл накладной.');
    } finally {
      busyRef.current=false;
      if (mountedRef.current) {
        setUploading(false);
        onBusy?.(false);
      }
    }
  };
  const pick=event=>{
    const files=Array.from(event.target.files || []);
    event.target.value='';
    attach(files);
  };
  const retry=()=>{
    const pending=pendingRef.current;
    if (pending && pending.owner===scope()) attach(pending.files);
    else {
      pendingRef.current=null;
      setError('Компания или склад изменились. Выберите файл заново.');
    }
  };
  const buttonStyle={minHeight:'44px',padding:'8px 14px',borderRadius:'8px',fontSize:'13px',
    border:'1.5px solid '+C.infoBorder,backgroundColor:C.infoLight,color:C.info,
    cursor:uploading?'wait':'pointer',opacity:uploading?0.65:1};
  const attachments=[...new Set([...(newInvoice.photoUrls || []),...(newInvoice.photos || []),
    ...(newInvoice.photoUrl ? [newInvoice.photoUrl] : [])])];
  return <div style={{margin:'12px 0',gridColumn:'1 / -1'}}>
    <div style={{display:'flex',gap:'8px',alignItems:'center',flexWrap:'wrap'}}>
      <input ref={galleryRef} aria-label="Вложения накладной" type="file" accept={invoiceImageAccept} multiple style={{display:'none'}} onChange={pick}/>
      <input ref={cameraRef} aria-label="Фото вложения с камеры" type="file" accept="image/*" multiple capture="environment" style={{display:'none'}} onChange={pick}/>
      <button type="button" disabled={uploading} style={buttonStyle} onClick={()=>galleryRef.current?.click()}>📎 PDF/фото из галереи</button>
      <button type="button" disabled={uploading} style={buttonStyle} onClick={()=>cameraRef.current?.click()}>📷 Камера</button>
      {uploading && <span role="status">Загружаем вложения…</span>}
      {attachments.map((url,index)=><a key={index} href={fileSrc(url)} target="_blank" rel="noreferrer"
        onClick={event=>{if (setShowPhotoModal && /\.(jpe?g|png|webp|heic|heif)(?:$|[?#])/i.test(url)) {event.preventDefault();setShowPhotoModal(fileSrc(url));}}}
        style={{color:C.info,fontSize:'12px'}}>Вложение {index+1}</a>)}
    </div>
    {error && <div role="alert" style={{marginTop:'8px',color:C.text,fontSize:'13px'}}>
      <p>{error}</p>
      {pendingRef.current && <button type="button" disabled={uploading} style={buttonStyle} onClick={retry}>Повторить загрузку вложений</button>}
    </div>}
  </div>;
}
