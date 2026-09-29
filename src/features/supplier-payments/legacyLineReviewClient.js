const positiveId=value=>Number.isSafeInteger(value) && value>0;
export function createLegacyLineReviewClient({API,userId,companyId,invoiceId},{fetcher=window.fetch,
 storage=window.localStorage,locks=window.navigator.locks,signal}={}) {
 if(![userId,companyId,invoiceId].every(positiveId))throw new Error('Не определён контекст счёта.');
 const key=`supplier-legacy-lines:v1:${API}:${userId}:${companyId}:${invoiceId}`;
 const path=`/supplier-invoices/${invoiceId}/legacy-line-review`;
 const headers={'X-Company-Id':String(companyId),'X-Company-Mode':'company'};
 const pending=()=>{
  const raw=storage.getItem(key);if(!raw)return null;
  const value=JSON.parse(raw);
  if(value.userId!==userId || value.companyId!==companyId || value.invoiceId!==invoiceId
    || !value.body?.requestId || !Array.isArray(value.body.lines) || value.body.confirmed!==true)
   throw new Error('Сохранённая сверка повреждена. Требуется проверка.');
  return value.body;
 };
 const request=async(url,options={})=>{
  const response=await fetcher(API+url,{credentials:'include',signal:signal?.(),...options,
   headers:{...headers,...options.headers}});
  const data=await response.json();
  if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:data.detail?.message || 'Не удалось выполнить сверку.');error.detail=data.detail;error.status=response.status;throw error;}
  return data;
 };
 const scoped=value=>value?.companyId===companyId && value?.invoiceId===invoiceId;
 const load=async()=>{const value=await request(path);if(!scoped(value))throw new Error('Ответ относится к другому счёту.');return value;};
 const upload=async file=>{
  const form=new FormData();form.append('file',file);form.append('context','supplier-invoice');
  const result=await request('/upload-photo',{method:'POST',body:form});
  if(result.companyId!==companyId || !positiveId(result.fileId))throw new Error('Не подтверждена компания оригинала.');
  return result;
 };
 const save=async body=>{
  if(!locks?.request)throw new Error('Для безопасного сохранения нужен актуальный браузер.');
  return locks.request(key,{mode:'exclusive',ifAvailable:true},async lock=>{
   if(!lock)throw new Error('Сверка выполняется в другой вкладке.');
   const previous=pending(),encoded=JSON.stringify(body);
   if(previous && JSON.stringify(previous)!==encoded)throw new Error('Сначала проверьте сохранённый запрос.');
   if(!previous){const raw=JSON.stringify({userId,companyId,invoiceId,body});storage.setItem(key,raw);if(storage.getItem(key)!==raw)throw new Error('Не удалось сохранить запрос до отправки.');}
   const release=()=>{if(JSON.stringify(pending())!==encoded)throw new Error('Запрос изменился в другой вкладке.');storage.removeItem(key);};
   let result;
   try{result=await request(path,{method:'POST',headers:{'Content-Type':'application/json'},body:encoded});}
   catch(error){
    if((error.detail?.code==='legacy_line_review_not_saved' && scoped(error.detail) && error.detail.requestId===body.requestId)
       || (error.status===422 && !previous)){release();error.message+=' Сверка не сохранена. Проверьте поля.';}
    throw error;
   }
   if(!scoped(result) || result.requestId!==body.requestId || result.reviewed!==true || !positiveId(result.specId))
    throw new Error('Ответ требует сверки. Повторите сохранённый запрос.');
   release();return result;
  });
 };
 return {pending,load,upload,save};
}
