import {useEffect,useRef,useState} from 'react';
import useAsyncSubmit from '../../hooks/useAsyncSubmit';
import SupplierHistoryMergeDialog from './SupplierHistoryMergeDialog';

const labels={supplier_invoices:'Счета',warehouse_invoices:'Накладные',supplier_offers:'Предложения'};
export default function SupplierDuplicateMerge({prefix,source,btnG,btnO,inp,onClose,onDone}) {
  const [query,setQuery]=useState(''),[items,setItems]=useState(null),[hasMore,setHasMore]=useState(false);
  const [offset,setOffset]=useState(0),[target,setTarget]=useState(null),[review,setReview]=useState(null);
  const [checked,setChecked]=useState(false),[reason,setReason]=useState(''),[history,setHistory]=useState(false);
  const [notice,setNotice]=useState('');
  const active=useRef(true);
  useEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
  const {submit,pending,error}=useAsyncSubmit(async(action,page=0)=>{
    setNotice('');
    let path=prefix+'/participants?search='+encodeURIComponent(query.trim())+'&limit=25&offset='+page;
    let options;
    if(action!=='search'){
      path=prefix+'/participants/'+source.id+'/duplicate-'+({confirm:'merge',completeInn:'complete-inn',review:'preview'}[action]);
      options={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(action!=='review'?
        {targetSupplierId:target.id,expectedReview:review.reviewVersion,confirmed:true,reason:reason.trim()}:{targetSupplierId:target.id})};
    }
    const response=await fetch(path,options),body=await response.json().catch(()=>({}));
    if(!active.current)return;
    if(!response.ok){if(response.status===409){setReview(null);setChecked(false);}throw new Error(typeof body.detail==='string'?body.detail:'Не удалось проверить карточки');}
    if(action==='search'){
      if(!Array.isArray(body.items))throw new Error('Не удалось загрузить каталог');
      setItems(body.items.filter(item=>item.id!==source.id&&!item.merged_into_supplier_id));setHasMore(body.hasMore);setOffset(page);
    }else if(action==='review'){
      if(body.sourceId!==source.id||body.targetId!==target.id||!body.reviewVersion||!body.documents)throw new Error('Проверка неполная. Повторите запрос.');
      setReview(body);setChecked(false);
    }else{
      if(!body.ok||body.sourceId!==source.id||body.targetId!==target.id)throw new Error('Проверьте результат перед повторной отправкой');
      if(action==='completeInn'){
        if(body.inn!==review.sourceInn)throw new Error('Проверьте результат сохранения ИНН');
        setReview(null);setChecked(false);setReason('');
        setNotice('ИНН сохранён. Теперь повторно проверьте последствия объединения и доступ к истории.');
      }else onDone();
    }
  });
  return <section aria-label="Объединение дубля" className="organization-participants__detail">
    <h4>Объединить дубли</h4>
    <p>Дубль: <strong>{source.name}</strong>. Выберите основную карточку этого поставщика в этой организации.</p>
    <p>Основной выбирайте карточку с кабинетом, а если кабинета нет — с проверенным ИНН. Остальные дубли можно присоединить к ней по очереди.</p>
    <form onSubmit={e=>{e.preventDefault();submit('search',0);}}>
      <label>Название или ИНН основной карточки<input style={inp} value={query} disabled={pending} maxLength={100}
        onChange={e=>{setQuery(e.target.value);setItems(null);setTarget(null);setReview(null);setChecked(false);}}/></label>
      <button style={btnG} disabled={pending} type="submit">Найти основную карточку</button>
    </form>
    {items&&<>
      {items.length===0&&<p>На этой странице нет подходящих карточек. Измените поиск или перейдите дальше.</p>}
      <ul className="organization-participants__list">{items.map(item=><li key={item.id}>
        <button type="button" style={btnG} disabled={pending} aria-pressed={target?.id===item.id}
          onClick={()=>{setTarget(item);setReview(null);setChecked(false);}}>{item.name} · ИНН: {item.inn||'не указан'} · {item.has_account?'с кабинетом':'без кабинета'} · №{item.id}</button>
      </li>)}</ul>
      <div className="organization-participants__toolbar">
        <button style={btnG} disabled={pending||offset===0} onClick={()=>submit('search',Math.max(0,offset-25))}>Предыдущие карточки</button>
        <button style={btnG} disabled={pending||!hasMore} onClick={()=>submit('search',offset+25)}>Следующие карточки</button>
      </div>
    </>}
    {target&&<p>Основная карточка: <strong>{target.name}</strong> · №{target.id}</p>}
    {review&&<>
      <p>С основной карточкой будут связаны документы дубля:</p>
      <ul>{Object.entries(labels).map(([key,label])=><li key={key}>{label}: {review.documents[key]||0}</li>)}</ul>
      <p>Номера документов, сохранённые реквизиты и суммы оплат останутся прежними.</p>
      {review.hasSupplierAccount?<>
        <p>У основной карточки есть кабинет. Перед объединением нужно проверить доступ к старой истории.</p>
        {review.innCompletionBlocker?<>
          <p role="status">{review.innCompletionBlocker}</p>
          <button type="button" style={btnG} disabled={pending} onClick={()=>submit('review')}>Повторить проверку реквизитов</button>
        </>:review.canCompleteInn?<p>В основной карточке ИНН не заполнен. В карточке-дубле указан <strong>{review.sourceInn}</strong>. Проверьте этот ИНН по счёту или договору кабинета. Изменение применяется к профилю поставщика для новых операций; старые документы не переписываются.</p>:
          <button style={btnO} disabled={pending} onClick={()=>setHistory(true)}>Проверить доступ к истории</button>}
      </>:null}
      {(!review.hasSupplierAccount||review.canCompleteInn)&&<>

        <label><input type="checkbox" checked={checked} disabled={pending} onChange={e=>setChecked(e.target.checked)}/> {review.canCompleteInn?'Я сверил ИНН по документу кабинета; это тот же поставщик':'Карточки и документы относятся к одному поставщику'}</label>
        <label>Основание объединения<textarea style={inp} rows={3} maxLength={1000} value={reason} disabled={pending} onChange={e=>setReason(e.target.value)}/></label>
        <button style={btnO} disabled={pending||!checked||reason.trim().length<10} onClick={()=>submit(review.canCompleteInn?'completeInn':'confirm')}>{review.canCompleteInn?'Заполнить пропущенный ИНН':'Объединить карточки'}</button>
      </>}
    </>}
    {notice&&<p role="status">{notice}</p>}
    {error&&<p role="alert">{error}</p>}
    <div className="organization-participants__toolbar">
      {target&&!review&&<button style={btnO} disabled={pending} onClick={()=>submit('review')}>Проверить последствия</button>}
      <button style={btnG} disabled={pending} onClick={onClose}>Закрыть объединение</button>
    </div>
    {history&&review&&<SupplierHistoryMergeDialog prefix={prefix} sourceId={source.id} targetId={target.id}
      sourceName={source.name} targetName={target.name} onClose={()=>setHistory(false)} onDone={onDone}/>}
  </section>;
}
