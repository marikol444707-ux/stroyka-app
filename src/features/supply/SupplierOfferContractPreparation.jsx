import React,{useEffect,useState} from 'react';
import SupplierContractReviewPanel from '../supplier-payments/SupplierContractReviewPanel';
import './supplierContractPreparation.css';

export default function SupplierOfferContractPreparation({API,user,companyContext,request,offer}) {
 const companyId=Number(companyContext?.selectedCompanyId || companyContext?.selectedCompany?.companyId);
 const role=companyContext?.selectedCompany?.role || user?.role;
 if(process.env.REACT_APP_SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED!=='true'
   || companyContext?.loading || companyContext?.mode==='all_companies'
   || companyContext?.selectedCompany?.readOnly || companyContext?.selectedCompany?.active===false
   || !['директор','зам_директора','снабженец','бухгалтер'].includes(role)
   || !Number.isSafeInteger(companyId) || companyId<=0 || companyId!==request.companyId
   || (offer.companyId!=null && offer.companyId!==companyId) || offer.status!=='Утверждено')return null;
 return <Preparation key={`${API}:${user.id}:${role}:${companyId}:${offer.id}`} API={API} userId={user.id} companyId={companyId} offerId={offer.id}/>;
}
function Preparation(props){
 const {API,companyId,offerId}=props;
 const [open,setOpen]=useState(false),[state,setState]=useState({loading:true}),[reload,setReload]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();let live=true;
  setState({loading:true});
  const get=async suffix=>{
   const response=await fetch(`${API}/supplier-offers/${offerId}${suffix}`,{credentials:'include',cache:'no-store',signal:controller.signal,
    headers:{'X-Company-Id':String(companyId),'X-Company-Mode':'company'}});
   const data=await response.json();
   if(!response.ok)throw new Error('Не удалось загрузить договор.');
   return data;
  };
  (async()=>{
   const history=await get('/contracts?limit=1');
   if(!Array.isArray(history.items))throw new Error('Не удалось загрузить договор.');
   const contract=history.items[0];
   if(!contract){if(live)setState({loading:false});return;}
   const parties=await get('/parties');
   if(contract.companyId!==companyId || contract.offerId!==offerId || parties.companyId!==companyId || parties.offerId!==offerId
     || !Number.isSafeInteger(contract.id) || contract.id<=0 || contract.status!=='reviewed')throw new Error('Не удалось подтвердить принадлежность договора.');
   if(live)setState({loading:false,contract,changed:contract.partyVersion!==parties.version});
  })().catch(error=>{if(live)setState({loading:false,error:error.message});});
  return()=>{live=false;controller.abort();};
 },[API,companyId,offerId,reload]);
 const contract=state.contract;
 return <div className="supplier-contract-preparation">
  {!open && <>
   {state.loading && <p role="status">Загружаем договор…</p>}
   {state.error && <><p role="alert">{state.error}</p><button type="button" onClick={()=>setReload(v=>v+1)}>Повторить загрузку</button></>}
   {!state.loading && !state.error && (contract && !state.changed ? <>
    <p role="status">Договор № {contract.snapshot?.number} от {contract.snapshot?.date} подключён. Для следующих счетов он используется автоматически.</p>
    {Number.isSafeInteger(contract.sourceFileId) && contract.sourceFileId>0 && <a href={`${API}/tenant-files/${contract.sourceFileId}/content`} target="_blank" rel="noopener noreferrer">Открыть договор</a>}
    <details><summary>Изменить договор</summary><p>Только если договор заменён или заключено допсоглашение.</p><button type="button" onClick={()=>setOpen(true)}>Открыть договор для изменения</button></details>
   </> : <>
    {state.changed && <p role="status">Стороны сделки изменились. Выберите договор для новых сторон.</p>}
    <button type="button" onClick={()=>setOpen(true)}>{state.changed?'Выбрать договор':'Добавить договор'}</button>
    {!state.changed && <p>Добавьте договор один раз. Для следующих КП и счетов он подставится автоматически, если подходит к сделке.</p>}
   </>)}
  </>}
  {open && <SupplierContractReviewPanel {...props} onClose={()=>setOpen(false)} onSaved={()=>{setOpen(false);setReload(v=>v+1);}}/>}
 </div>;
}
