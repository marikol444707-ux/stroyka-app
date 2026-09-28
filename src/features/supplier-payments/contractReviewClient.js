const fail = message => { throw new Error(message); };
const id = value => Number.isSafeInteger(value) && value > 0;
const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);
export const legalFields = ['fullName','inn','kpp','ogrn','legalAddress','bankName','bik','rs','ks','directorName','directorPosition','basis','phone','email'];
export const legalDraft = source => Object.fromEntries(legalFields.map(key=>[key,String(source?.[key] || '')]));

export function createContractReviewClient(scope, {fetcher=window.fetch,storage=window.localStorage,
  locks=window.navigator.locks,signal}={}) {
  const {API,userId,companyId,offerId}=scope;
  if (![userId,companyId,offerId].every(id)) fail('Не определены сотрудник, компания или КП.');
  const key=`supplier-contract-review:v1:${API}:${userId}:${companyId}:${offerId}`;
  const base=`/supplier-offers/${offerId}`;
  const headers={'X-Company-Id':String(companyId),'X-Company-Mode':'company'};
  const request=async(path,{method='GET',body,form}={})=>{
    const response=await fetcher(API+path,{credentials:'include',signal:typeof signal==='function'?signal():signal,method,
      headers:{...headers,...(body?{'Content-Type':'application/json'}:{})},body:form || (body?JSON.stringify(body):undefined)});
    const data=await response.json();
    if (!response.ok) {
      const error=new Error(typeof data?.detail==='string'?data.detail:
        typeof data?.detail?.message==='string'?data.detail.message:'Не удалось сохранить данные. Проверьте поля и доступ.');
      error.status=response.status;throw error;
    }
    return data;
  };
  const pending=()=>{
    const raw=storage.getItem(key);if(!raw)return null;
    let value;try{value=JSON.parse(raw);}catch(_){fail('Сохранённая проверка повреждена. Требуется сверка.');}
    if(value.companyId!==companyId || value.userId!==userId || value.offerId!==offerId
        || !['parties','contract'].includes(value.kind) || !value.body
        || !Number.isSafeInteger(value.body.expectedVersion) || value.body.expectedVersion<0) {
      fail('Сохранённая проверка относится к другому контексту или повреждена.');
    }
    return value;
  };
  const verify=(kind,body,value)=>{
    if(value?.companyId!==companyId || value?.offerId!==offerId || value.version!==body.expectedVersion+1
        || value.reason!==body.reason) return false;
    if(kind==='parties')return value.buyerCompanyId===body.buyerCompanyId && value.payerCompanyId===body.payerCompanyId;
    return id(value.id) && value.status==='reviewed' && value.partyVersion===body.partyVersion
      && value.sourceFileId===body.sourceFileId && value.snapshot
      && (value.snapshot.reusedFrom?.contractId || null)===(body.reusedFromContractId || null)
      && (body.applicability ? ['scope','projectId','term','startsOn','endsOn'].every(k=>(value.snapshot.applicability?.[k] ?? null)===(body.applicability[k] ?? null)) : !value.snapshot.applicability)
      && ['number','date','paymentTerms'].every(k=>value.snapshot[k]===body[k])
      && ['buyer','payer','supplier'].every(side=>legalFields.every(k=>value.snapshot[side]?.[k]===body[side]?.[k]));
  };
  const save=async(kind,body)=>{
    if(!['parties','contract'].includes(kind) || !Number.isSafeInteger(body?.expectedVersion)
      || body.expectedVersion<0 || !body.reason?.trim()) fail('Проверьте версию и основание сохранения.');
    if(!locks?.request)fail('Для безопасного сохранения нужен актуальный браузер.');
    return locks.request(key,{mode:'exclusive',ifAvailable:true},async lock=>{
      if(!lock)fail('Сохранение уже выполняется в другой вкладке.');
      const previous=pending();
      if(previous && (previous.kind!==kind || !same(previous.body,body)))fail('Сначала проверьте результат сохранённого запроса.');
      const command={userId,companyId,offerId,kind,body};
      const raw=JSON.stringify(command);
      if(!previous){storage.setItem(key,raw);if(storage.getItem(key)!==raw)fail('Не удалось сохранить запрос до отправки.');}
      const release=()=>{
        if(!same(pending(),command))fail('Запрос изменился в другой вкладке. Откройте счёт заново.');
        storage.removeItem(key);
      };
      let result;
      try{result=await request(base+(kind==='parties'?'/parties':'/contracts'),{method:kind==='parties'?'PUT':'POST',body});}
      catch(error){
        // An initial schema rejection cannot have committed this command.
        // A retry may follow a lost successful response, so retain it.
        if(error.status===422 && !previous){release();throw error;}
        if(error.status!==409)throw error;
        const path=kind==='parties'?'/parties/history':'/contracts';
        const history=await request(`${base}${path}?beforeVersion=${body.expectedVersion+2}&limit=1`);
        result=history?.items?.[0];
        if(!verify(kind,body,result)){
          // Immutable exact revision occupied by a different command proves
          // ours did not commit. Never use a foreign or missing row as proof.
          if(result?.companyId===companyId && result?.offerId===offerId
              && result?.version===body.expectedVersion+1){
            release();error.reloadContext=true;
            error.message='Другой сотрудник сохранил эту версию. Данные обновлены; проверьте их перед повторным сохранением.';
          }
          throw error;
        }
      }
      if(!verify(kind,body,result))fail('Ответ не совпадает с проверенными данными. Сохранённый запрос оставлен для сверки.');
      release();return result;
    });
  };
  const upload=async file=>{
    const form=new FormData();form.append('file',file);form.append('context','supplier-contract');
    const result=await request('/upload-photo',{method:'POST',form});
    if(!id(result.fileId) || result.companyId!==companyId)fail('Файл не подтверждён в выбранной компании.');
    return result;
  };
  const load=async()=>{
    const [parties,context]=await Promise.all([request(base+'/parties'),request('/users/company-context')]);
    if(parties.companyId!==companyId || parties.offerId!==offerId || !Number.isSafeInteger(parties.version))fail('Стороны относятся к другой сделке.');
    const companies=(context.companies||[]).filter(c=>id(c.companyId) && c.active!==false && c.companyActive!==false && !c.readOnly);
    return {parties,companies};
  };
  const reviewContext=async()=>{
    const value=await request(base+'/contract-review-context');
    if(value.companyId!==companyId || value.offerId!==offerId || !id(value.partyVersion)
       || !Number.isSafeInteger(value.expectedVersion) || value.expectedVersion<0)fail('Контекст проверки договора изменился.');
    if(value.existingOriginal && (!id(value.existingOriginal.sourceFileId)
       || value.existingOriginal.version!==value.expectedVersion))fail('Версия сохранённого оригинала изменилась.');
    for(const contract of value.reusableContracts || []){
      if(contract.companyId!==companyId || !id(contract.id) || !id(contract.offerId)
         || !id(contract.sourceFileId) || !id(contract.version) || !contract.snapshot
         || ['buyer','payer','supplier'].some(side=>contract.snapshot[side]?.inn!==value[side]?.inn)
         || ['buyer','payer'].some(side=>contract.snapshot[side]?.companyId!==value[side]?.companyId)
         || contract.snapshot.supplier?.supplierId!==value.supplier?.supplierId)
        fail('Сохранённый договор относится к другим сторонам.');
    }
    return value;
  };
  const recognize=async(fileId,context)=>{
    const body={sourceFileId:fileId,partyVersion:context.partyVersion,expectedVersion:context.expectedVersion};
    const value=await request(base+'/contract-recognition',{method:'POST',body});
    if(value.companyId!==companyId || value.offerId!==offerId || value.sourceFileId!==fileId
      || value.partyVersion!==body.partyVersion || value.expectedVersion!==body.expectedVersion
      || !/^[a-f0-9]{64}$/.test(value.sourceContentHash || '') || value.reviewConfirmed!==false
      || value.appliedToAccounting!==false || !value.parties)fail('Результат распознавания не соответствует договору.');
    for(const side of ['buyer','payer','supplier']){
      const party=value.parties[side];
      if(!party || !['matched','missing','ambiguous','identity_mismatch'].includes(party.status) || !party.fields)fail('Некорректный результат распознавания.');
      for(const [key,item] of Object.entries(party.fields)){
        if(!legalFields.includes(key) || typeof item?.value!=='string' || item.value.length>2000
          || !Number.isSafeInteger(item.line) || item.line<1 || typeof item.quote!=='string')fail('Некорректный реквизит договора.');
      }
    }
    return value;
  };
  return {pending,save,upload,load,reviewContext,recognize};
}
