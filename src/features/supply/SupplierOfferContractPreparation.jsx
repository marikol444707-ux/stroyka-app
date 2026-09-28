import React,{useState} from 'react';
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
 const [open,setOpen]=useState(false),[saved,setSaved]=useState(false);
 return <div className="supplier-contract-preparation">
  {!open && <button type="button" onClick={()=>setOpen(true)}>Проверить договор до выставления счёта</button>}
  {saved && !open && <p role="status">Версия договора сохранена. Поставщик сможет выбрать её при выставлении счёта.</p>}
  {open && <SupplierContractReviewPanel {...props} onClose={()=>setOpen(false)} onSaved={()=>{setSaved(true);setOpen(false);}}/>}
 </div>;
}
