import React,{useEffect,useRef,useState} from 'react';
export default function SupplierInvoiceContractChoice(props){
 if(process.env.REACT_APP_SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED!=='true')return null;
 return <Choice key={`${props.API}:${props.userId}:${props.companyId}:${props.offerId}`} {...props}/>;
}
function Choice({API,offerId,companyId,value,onChange,disabled}){
 const [state,setState]=useState({loading:true}),[reload,setReload]=useState(0);
 const changed=useRef(onChange);changed.current=onChange;
 useEffect(()=>{
  const controller=new AbortController();let live=true;
  changed.current(null);setState({loading:true});
  const get=async path=>{
   const response=await fetch(`${API}/supplier-offers/${offerId}${path}`,{credentials:'include',cache:'no-store',signal:controller.signal});
   const data=await response.json();
   if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Не удалось загрузить договор.');
   return data;
  };
  Promise.all([get('/contracts?limit=1'),get('/parties')]).then(([history,parties])=>{
   if(!live)return;
   if(parties.companyId!==companyId || parties.offerId!==offerId)throw new Error('Стороны относятся к другой сделке.');
   const contract=history.items?.[0];
   if(!contract){setState({loading:false,error:'Заказчик ещё не передал договор. Попросите его проверить версию и нажать «Передать поставщику» в архиве документов.'});return;}
   if(contract.companyId!==companyId || contract.offerId!==offerId || !Number.isSafeInteger(contract.id) || contract.id<=0 || contract.status!=='reviewed')throw new Error('Версия договора не подтверждена для этой сделки.');
   if(contract.partyVersion!==parties.version)throw new Error('Стороны изменились. Заказчику нужно проверить новую версию договора.');
   setState({loading:false,contract});
  }).catch(error=>{if(live)setState({loading:false,error:error.message});});
  return()=>{live=false;controller.abort();};
 },[API,companyId,offerId,reload]);
 const contract=state.contract;
 return <fieldset disabled={disabled || state.loading} style={{minWidth:0,margin:'12px 0'}}>
  <legend>Договор для счёта</legend>
  {state.loading && <p role="status">Загрузка проверенной версии…</p>}
  {state.error && <p role="alert">{state.error}</p>}
  {contract && <>
   <p>№ {contract.snapshot?.number} от {contract.snapshot?.date}, версия {contract.version}</p>
   <p>Покупатель: {contract.snapshot?.buyer?.fullName}.{!(contract.snapshot?.buyer?.companyId && contract.snapshot.buyer.companyId===contract.snapshot?.payer?.companyId)&&` Плательщик: ${contract.snapshot?.payer?.fullName}.`}</p>
   {Number.isSafeInteger(contract.sourceFileId)&&<p><a href={`${API}/tenant-files/${contract.sourceFileId}/content`} target="_blank" rel="noopener noreferrer">Основной договор</a></p>}
   {contract.snapshot?.addenda?.map(a=>Number.isSafeInteger(a.sourceFileId)&&<p key={a.sourceFileId}><a href={`${API}/tenant-files/${a.sourceFileId}/content`} target="_blank" rel="noopener noreferrer">Допсоглашение № {a.number}</a></p>)}
   <label><input type="checkbox" checked={value===contract.id} onChange={e=>changed.current(e.target.checked?contract.id:null)}/>Выставить счёт по этой версии договора</label>
  </>}
  <button type="button" onClick={()=>{changed.current(null);setState({loading:true});setReload(v=>v+1);}}>Обновить договор</button>
 </fieldset>;
}
