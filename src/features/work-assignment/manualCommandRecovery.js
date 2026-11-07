import { useLayoutEffect, useRef, useState } from 'react';
import { commandUuid } from '../../utils/commandUuid';
import { journalScopeKey } from '../../hooks/useJournalMutation';

const prefix = 'stroyka:manual-brigade-command:v1:';
const changed = 'stroyka:manual-brigade-command-changed';
const inFlight = new Set();
const positive = value => (typeof value==='number' || (typeof value==='string' && /^[1-9][0-9]*$/.test(value)))
  && Number.isSafeInteger(Number(value)) && Number(value) > 0;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const packageName = value => String(value || 'Основная').trim() || 'Основная';

export function manualCommandScope(context, user, kind, source) {
  if (context?.mode !== 'company' || ![context.selectedCompanyId,user?.id,source?.id].every(positive)) return null;
  const companyId = Number(context.selectedCompanyId);
  if (source.companyId != null && Number(source.companyId) !== companyId) return null;
  return {companyId,userId:Number(user.id),kind,sourceId:Number(source.id),
    projectId:kind==='contract' ? Number(source.id) : positive(source.projectId) ? Number(source.projectId) : null,
    workPackage:packageName(source.workPackage)};
}

function keyFor(scope) {
  if (!scope || !['contract','assignment'].includes(scope.kind)) throw new Error('Выберите компанию и откройте объект заново.');
  return prefix + [scope.userId,scope.companyId,scope.kind,scope.sourceId,encodeURIComponent(scope.workPackage)].join(':');
}
const pathFor = scope => scope.kind==='contract' ? '/brigade-contracts' : `/estimates/${scope.sourceId}/work-assignment`;
const reference = (scope,payload) => scope.kind==='contract' ? payload.contractorRef : payload.assignee?.contractorRef;
const corrupt = () => new Error('Сохранённая отправка повреждена. Новая отправка заблокирована; проверьте договоры.');

function validateReceipt(scope, command, result) {
  const id = scope.kind==='contract' ? result?.id : result?.contractId;
  if (result?.ok !== true || !positive(id) || result.companyId !== scope.companyId
    || !positive(result.projectId) || (scope.projectId && result.projectId !== scope.projectId)
    || result.manualRequestId !== reference(scope,JSON.parse(command.body)).requestId) {
    throw new Error('Сервер не подтвердил исходную отправку. Повторите сохранённую отправку.');
  }
}

export function readManualCommand(scope, storage = sessionStorage) {
  const raw = storage.getItem(keyFor(scope));
  if (raw === null) return null;
  try {
    if (raw.length > 600000) throw corrupt();
    const command = JSON.parse(raw);
    if (command.version !== 1 || JSON.stringify(command.scope) !== JSON.stringify(scope)
      || command.path !== pathFor(scope) || typeof command.body !== 'string'
      || typeof command.attempted !== 'boolean') throw corrupt();
    const payload = JSON.parse(command.body);
    const ref = reference(scope,payload);
    if (ref?.type !== 'manual' || !uuid.test(ref.requestId) || Object.keys(ref).length !== 2
      || payload.expectedCompanyId !== scope.companyId || payload.expectedActorId !== scope.userId
      || (scope.kind==='contract' ? payload.projectId !== scope.sourceId || payload.contractorId !== null
        || packageName(payload.workPackage) !== scope.workPackage
        : payload.assignee?.contractorId !== null || !Array.isArray(payload.items) || !payload.items.length)) throw corrupt();
    if (command.receipt) validateReceipt(scope,command,command.receipt);
    return command;
  } catch (_) { throw corrupt(); }
}

function save(scope, command, storage = sessionStorage) {
  const raw = JSON.stringify(command);
  if (raw.length > 600000) throw new Error('Отправка слишком большая для восстановления в браузере.');
  storage.setItem(keyFor(scope),raw);
  if (storage.getItem(keyFor(scope)) !== raw) throw new Error('Браузер не сохранил отправку. Запрос не отправлен.');
  window.dispatchEvent(new Event(changed));
}

export function prepareManualCommand(scope, payload) {
  if (readManualCommand(scope)) throw new Error('Сначала завершите сохранённую отправку.');
  const copy = JSON.parse(JSON.stringify(payload));
  const ref = {type:'manual',requestId:commandUuid()};
  if (scope.kind==='contract') copy.contractorRef=ref;
  else copy.assignee.contractorRef=ref;
  copy.expectedCompanyId=scope.companyId;
  copy.expectedActorId=scope.userId;
  const command = {version:1,scope,path:pathFor(scope),body:JSON.stringify(copy),attempted:false,receipt:null};
  save(scope,command);
  return readManualCommand(scope);
}

export async function executeManualCommand({API,scope,signal,fetchFn=window.fetch}) {
  const key=keyFor(scope);
  if(inFlight.has(key)) throw new Error('Эта отправка ещё выполняется.');
  inFlight.add(key);
  try {
    const command=readManualCommand(scope);
    if(!command) throw new Error('Нет сохранённой отправки.');
    if(command.receipt) return command;
    const attempted=command.attempted;
    command.attempted=true;
    save(scope,command);
    const response=await fetchFn(API+command.path,{method:'POST',credentials:'include',signal,
      headers:{'Content-Type':'application/json','X-Company-Id':String(scope.companyId),'X-Company-Mode':'company'},body:command.body})
      .catch(error=>{if(error?.name==='AbortError')throw error;
        throw new Error('Связь прервалась. Проверьте соединение и повторите сохранённую отправку.');});
    const result=await response.json().catch(()=>null);
    if(!response.ok) {
      if(!attempted && [400,422].includes(response.status)) {
        sessionStorage.removeItem(key);
        window.dispatchEvent(new Event(changed));
      }
      throw new Error(typeof result?.detail==='string'?result.detail:'Не удалось подтвердить отправку. Повторите сохранённую отправку.');
    }
    validateReceipt(scope,command,result);
    command.receipt=result;
    save(scope,command);
    return command;
  } finally { inFlight.delete(key); }
}

export function finishManualCommand(scope, body) {
  const current=readManualCommand(scope);
  if(!current?.receipt || current.body!==body) throw new Error('Подтверждение отправки изменилось. Обновите страницу.');
  sessionStorage.removeItem(keyFor(scope));
  window.dispatchEvent(new Event(changed));
}

export function useManualCommandRecovery({API,user,companyContext,kind,source,enabled=true}) {
  const scope=manualCommandScope(companyContext,user,kind,source);
  const key=scope ? JSON.stringify(scope) : '';
  const tag=JSON.stringify([key,user?.role,companyContext?.selectedCompany?.role,enabled]);
  const latest=useRef(tag);
  latest.current=tag;
  const mounted=useRef(false);
  const epoch=useRef(0);
  const active=useRef(null);
  const openedBrowserScope=useRef(journalScopeKey());
  const read=()=>{try{return {key,pending:scope?readManualCommand(scope):null,error:''};}catch(error){return {key,pending:null,error:error.message};}};
  const [state,setState]=useState(read);
  const [runState,setRunState]=useState({key,busy:false,error:''});
  useLayoutEffect(()=>{
    mounted.current=true;
    epoch.current+=1;
    openedBrowserScope.current=journalScopeKey();
    const refresh=()=>setState(read());
    refresh();
    setRunState({key,busy:false,error:''});
    window.addEventListener(changed,refresh);
    window.addEventListener('storage',refresh);
    return ()=>{mounted.current=false;epoch.current+=1;active.current?.abort();active.current=null;
      window.removeEventListener(changed,refresh);window.removeEventListener('storage',refresh);};
  // Scope is serialized so changing object identities does not abort a request.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[tag]);
  const visible=state.key===key?state:read();
  const run=async({payload,apply,done})=>{
    if(active.current || !mounted.current || !enabled) return;
    const capturedEpoch=epoch.current;
    const browserScope=journalScopeKey();
    const controller=new AbortController();
    const current=()=>mounted.current && latest.current===tag && epoch.current===capturedEpoch
      && !controller.signal.aborted && journalScopeKey()===browserScope;
    active.current=controller;
    setRunState({key,busy:true,error:''});
    try {
      if(!scope) throw new Error('Выберите компанию и откройте объект заново.');
      const [storedUser,storedContext]=JSON.parse(browserScope);
      if(browserScope!==openedBrowserScope.current || (storedUser!=null && Number(storedUser)!==scope.userId)
        || (storedContext && (storedContext.mode!=='company' || storedContext.companyId!==scope.companyId))) {
        throw new Error('Пользователь или компания изменились. Откройте сохранённую отправку в исходном контексте.');
      }
      if(payload) prepareManualCommand(scope,payload);
      const command=await executeManualCommand({API,scope,signal:controller.signal});
      if(!current()) return;
      const applied=await apply(command.receipt,JSON.parse(command.body),current);
      if(!current()) return;
      finishManualCommand(scope,command.body);
      done?.(command.receipt,JSON.parse(command.body),applied);
    } catch(error) {
      if(current()) setRunState({key,busy:false,error:error.message || 'Связь прервалась. Повторите сохранённую отправку.'});
    } finally {
      if(active.current===controller){active.current=null;if(current())setRunState(previous=>({...previous,busy:false}));}
    }
  };
  return {scope,pending:visible.pending,error:visible.error || (runState.key===key?runState.error:''),
    busy:runState.key===key&&runState.busy,blocked:Boolean(visible.error),run};
}
