import React, {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import useAsyncSubmit from '../../hooks/useAsyncSubmit';

export default function SupplierMergeDialog({supplier, suppliers, API, C, onClose, loadAll}) {
  const [sourceId, setSourceId] = useState('');
  const [review, setReview] = useState(null);
  const [done, setDone] = useState(false);
  const dialog = useRef(null);
  const active = useRef(true);
  const {submit, pending, error} = useAsyncSubmit(async () => {
    const response = await fetch(API + '/suppliers/' + supplier.id + (review ? '/merge' : '/merge-preview'), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({companyId: supplier.companyId, sourceId: Number(sourceId),
        ...(review ? {targetVersion:review.targetVersion, sourceVersion:review.sourceVersion, expectedReview:review.reviewVersion, confirmed:true} : {})}),
    });
    const data = await response.json().catch(() => ({}));
    if (!active.current) return;
    if (!response.ok) {
      if(response.status===409) setReview(null);
      throw new Error(data.detail || 'Не удалось проверить объединение');
    }
    if (!review) {
      if(data.targetId!==supplier.id || data.sourceId!==Number(sourceId) || !Number.isInteger(data.targetVersion) || !Number.isInteger(data.sourceVersion) || !data.documents || typeof data.reviewVersion !== 'string' || !data.reviewVersion) throw new Error('Не удалось получить результат проверки. Обновите каталог.');
      setReview(data); return;
    }
    if (!data.ok) throw new Error('Не удалось подтвердить объединение. Обновите каталог перед повторной попыткой.');
    setDone(true);
    try { await loadAll(); } catch (_) { throw new Error('Карточки объединены, но список не обновился. Обновите страницу.'); }
    if (active.current) onClose();
  });
  useEffect(() => {
    active.current=true;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.current?.focus();
    return () => { active.current=false; document.body.style.overflow=overflow; previous?.focus(); };
  }, []);
  return createPortal(<div style={{position:'fixed',inset:0,zIndex:900,background:'rgba(15,23,42,.65)',display:'flex',alignItems:'center',justifyContent:'center',padding:12}}>
    <div ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="supplier-merge-title"
      onKeyDown={event => {
        if(event.key==='Escape' && !pending) onClose();
        if(event.key==='Tab') {
          const nodes=Array.from(dialog.current.querySelectorAll('button:not(:disabled),select:not(:disabled)'));
          const first=nodes[0], last=nodes[nodes.length-1];
          if(event.shiftKey && (document.activeElement===first || document.activeElement===dialog.current)) {event.preventDefault();last?.focus();}
          else if(!event.shiftKey && document.activeElement===last) {event.preventDefault();first?.focus();}
        }
      }} style={{background:C.card || C.bg,color:C.text,border:'1px solid '+C.border,borderRadius:16,boxSizing:'border-box',width:520,maxWidth:'100%',maxHeight:'85dvh',overflowY:'auto',padding:20}}>
      <h3 id="supplier-merge-title" style={{marginTop:0}}>Объединить карточки</h3>
      <p>Основная карточка: <b>{supplier.name}</b></p>
      <p style={{color:C.textSec}}>Счета, накладные и история останутся на месте и будут показаны вместе. Суммы оплат и банковские реквизиты сохранятся.</p>
      {!review && <label style={{display:'grid',gap:8}}>Карточка из накладной
        <select value={sourceId} disabled={pending} onChange={e=>setSourceId(e.target.value)} style={{minHeight:44,width:'100%',background:C.bg,color:C.text,border:'1px solid '+C.border,borderRadius:8,padding:8}}>
          <option value="">Выберите карточку</option>
          {suppliers.filter(item=>item.id!==supplier.id && !item.hasSupplierAccount && (!item.canonicalSupplierId || item.canonicalSupplierId===item.id)).map(item=><option key={item.id} value={item.id}>{item.name}{item.inn ? ' · ИНН '+item.inn : ''}</option>)}
        </select>
      </label>}
      {review && <div><p><b>{review.sourceName}</b> → <b>{review.targetName}</b></p>
        <p>Счета: {review.documents.supplier_invoices} · Накладные: {review.documents.warehouse_invoices} · Предложения: {review.documents.supplier_offers}</p>
        <p>{review.hasSupplierAccount ? 'Объединение с кабинетом: Администратор → Организации → Участники и доступ → Поставщики. Там проверяется доступ к старым документам.' : 'Ссылка из основной карточки подключит поставщика к общей истории.'}</p>
      </div>}
      {done && <p role="status">Карточки объединены. Если список не обновился, обновите страницу.</p>}
      {error && <p role="alert" style={{color:C.danger || '#dc2626'}}>{error}</p>}
      <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:18}}>
        <button type="button" disabled={pending} onClick={onClose} style={{minHeight:44}}>Закрыть</button>
        {review && !done && <button type="button" disabled={pending} onClick={()=>setReview(null)} style={{minHeight:44}}>Назад</button>}
        {!done && !review?.hasSupplierAccount && <button type="button" disabled={pending || !sourceId} onClick={submit} style={{minHeight:44,background:C.accent || '#f97316',color:'#fff',border:0,borderRadius:8,padding:'8px 16px'}}>{pending ? 'Подождите…' : review ? 'Подтвердить объединение' : 'Проверить карточки'}</button>}
      </div>
    </div>
  </div>, document.body);
}
