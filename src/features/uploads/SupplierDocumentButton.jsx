import React, {useCallback, useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {FileText, X, Download, ChevronLeft, ChevronRight, ZoomIn, ZoomOut} from 'lucide-react';
import {PREVIEW_INVALIDATED} from '../../hooks/usePreviewInvalidation';
import './supplierDocumentViewer.css';

const identity = value => value;
class DocumentViewError extends Error {}
export default function SupplierDocumentButton({url, fileSrc=identity, label='Открыть документ'}) {
  return url ? <DocumentButton key={`${url}:${fileSrc(url)}`} {...{url,fileSrc,label}}/> : null;
}
function DocumentButton({url,fileSrc,label}) {
  const [open,setOpen]=useState(false);
  const trigger=useRef(null);
  const onClose=useCallback(()=>{setOpen(false);trigger.current?.focus();},[]);
  return <>
    <button ref={trigger} type="button" className="supplier-document-open" onClick={()=>setOpen(true)}><FileText size={18}/>{label}</button>
    {open && <DocumentViewer {...{url,fileSrc,label}} onClose={onClose}/>}
  </>;
}
function DocumentViewer({url,fileSrc,label,onClose}) {
  const [state,setState]=useState({loading:true}),[attempt,setAttempt]=useState(0);
  const [page,setPage]=useState(1),[zoom,setZoom]=useState(1),[renderError,setRenderError]=useState('');
  const [resize,setResize]=useState(0);
  const resolvedUrl=fileSrc(url);
  useEffect(()=>{const update=()=>setResize(v=>v+1);window.addEventListener('resize',update);return()=>window.removeEventListener('resize',update);},[]);
  const canvas=useRef(null),body=useRef(null),dialog=useRef(null),close=useRef(null);
  useEffect(()=>{
    const before=document.body.style.overflow;document.body.style.overflow='hidden';close.current?.focus();
    const keyboard=event=>{
      if(event.key==='Escape'){event.preventDefault();onClose();}
      if(event.key==='Tab'){
        const elements=dialog.current?.querySelectorAll('button:not(:disabled),a[href]');
        if(!elements?.length)return;
        const first=elements[0],last=elements[elements.length-1];
        if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
        else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
      }
    };
    window.addEventListener('keydown',keyboard);window.addEventListener(PREVIEW_INVALIDATED,onClose);
    return()=>{document.body.style.overflow=before;window.removeEventListener('keydown',keyboard);window.removeEventListener(PREVIEW_INVALIDATED,onClose);};
  },[onClose]);
  useEffect(()=>{
    const controller=new AbortController();let objectUrl='',loadingTask,filename='Документ';
    setState({loading:true});setPage(1);setZoom(1);setRenderError('');
    (async()=>{
      if(!/^\/tenant-files\/[1-9]\d*\/content\/?$/.test(url) && !(/^\/uploads\/[^?#]+$/.test(url) && new URL(url,window.location.origin).pathname===url))throw new DocumentViewError('Ссылка на файл устарела. Прикрепите оригинал документа заново.');
      const response=await fetch(resolvedUrl,{credentials:'include',cache:'no-store',signal:controller.signal});
      if(!response.ok)throw new DocumentViewError(response.status===404?'Файл не найден. Прикрепите оригинал документа заново.':response.status===401?'Войдите в приложение и откройте документ ещё раз.':response.status===403?'Нет доступа к этому документу.':'Не удалось загрузить документ. Попробуйте ещё раз.');
      const blob=await response.blob();
      if(blob.size>50*1024*1024)throw new DocumentViewError('Файл слишком большой для просмотра. Размер должен быть до 50 МБ.');
      if(controller.signal.aborted)return;
      const bytes=new Uint8Array(await blob.arrayBuffer());
      const isPdf=String.fromCharCode(...bytes.subarray(0,5))==='%PDF-';
      const image=/^image\/(jpeg|png|webp|gif)$/.test(blob.type);
      if(!isPdf && !image)throw new DocumentViewError('Этот файл нельзя показать здесь. Для просмотра прикрепите PDF или фотографию.');
      objectUrl=URL.createObjectURL(blob);
      const encoded=response.headers?.get('Content-Disposition')?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      filename=isPdf?'Документ.pdf':'Документ';
      try{if(encoded)filename=Array.from(decodeURIComponent(encoded),char=>char.charCodeAt(0)<32 || char==='/' || char===String.fromCharCode(92)?'_':char).join('');}catch{/* retain safe name */}
      if(image){if(!controller.signal.aborted)setState({image:true,src:objectUrl,filename});return;}
      const {loadPdfDocument}=await import('./loadPdfDocument');
      if(controller.signal.aborted)return;
      loadingTask=await loadPdfDocument(bytes);
      if(controller.signal.aborted){loadingTask.destroy();return;}
      const pdf=await loadingTask.promise;
      if(!controller.signal.aborted)setState({pdf,src:objectUrl,filename});
    })().catch(error=>{
      if(controller.signal.aborted)return;
      const message=error instanceof DocumentViewError?error.message:error.name==='InvalidPDFException'?'PDF повреждён. Прикрепите оригинал документа заново.':error.name==='PasswordException'?'PDF защищён паролем. Скачайте его для открытия в другом приложении.':'Не удалось открыть документ. Попробуйте ещё раз или скачайте файл.';
      setState({error:message,src:objectUrl,filename});
    });
    return()=>{controller.abort();loadingTask?.destroy();if(objectUrl)URL.revokeObjectURL(objectUrl);};
  },[url,resolvedUrl,attempt]);
  useEffect(()=>{
    if(!state.pdf)return undefined;
    let stopped=false,renderTask;
    setRenderError('');
    (async()=>{
      const pdfPage=await state.pdf.getPage(page);if(stopped)return;
      const base=pdfPage.getViewport({scale:1});
      const width=Math.min(body.current.clientWidth-24,1100);
      const viewport=pdfPage.getViewport({scale:width/base.width*zoom});
      const ratio=Math.min(window.devicePixelRatio || 1,2,Math.sqrt(16000000/(viewport.width*viewport.height)));
      const node=canvas.current;node.width=Math.floor(viewport.width*ratio);node.height=Math.floor(viewport.height*ratio);
      node.style.width=viewport.width+'px';node.style.height=viewport.height+'px';
      renderTask=pdfPage.render({canvasContext:node.getContext('2d'),viewport,transform:[ratio,0,0,ratio,0,0]});
      await renderTask.promise;
    })().catch(error=>{if(!stopped)setRenderError('Не удалось показать страницу. Скачайте файл или попробуйте открыть заново.');});
    return()=>{stopped=true;renderTask?.cancel();};
  },[state.pdf,page,zoom,resize]);
  return createPortal(<div className="supplier-document-overlay"><section ref={dialog} role="dialog" aria-modal="true" aria-label={label} className="supplier-document-dialog">
    <header><strong>{label.replace(/^Открыть /,'').replace(/^./,char=>char.toUpperCase())}</strong><button ref={close} type="button" onClick={onClose} aria-label="Закрыть документ"><X size={20}/></button></header>
    {state.src && <div className="supplier-document-tools">
      {state.pdf && <><button type="button" disabled={page===1} onClick={()=>setPage(p=>p-1)} aria-label="Предыдущая страница"><ChevronLeft size={20}/></button><span aria-live="polite">{page} / {state.pdf.numPages}</span><button type="button" disabled={page===state.pdf.numPages} onClick={()=>setPage(p=>p+1)} aria-label="Следующая страница"><ChevronRight size={20}/></button>
      <button type="button" disabled={zoom<=1} onClick={()=>setZoom(z=>Math.max(1,z-.25))} aria-label="Уменьшить"><ZoomOut size={18}/></button><button type="button" disabled={zoom>=2} onClick={()=>setZoom(z=>Math.min(2,z+.25))} aria-label="Увеличить"><ZoomIn size={18}/></button></>}
      <a href={state.src} download={state.filename}><Download size={18}/>Скачать</a>
    </div>}
    <div ref={body} className="supplier-document-body">
      {state.loading && <p role="status">Открываем документ…</p>}
      {(state.error || renderError) && <div><p role="alert">{state.error || renderError}</p><button type="button" onClick={()=>setAttempt(a=>a+1)}>Попробовать ещё раз</button></div>}
      {state.pdf && <canvas ref={canvas} aria-label={`Страница ${page} документа`}/>}
      {state.image && <img src={state.src} alt="Документ поставщика" onError={()=>setRenderError('Не удалось показать фотографию. Скачайте файл.')}/>}
    </div>
  </section></div>,document.body);
}
