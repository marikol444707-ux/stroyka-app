import React, {useState} from 'react';
import SupplierContracts from './SupplierContracts';
import SupplyTechnicalComparisonPanel, {parseSupplyTechnicalComparisonCompanyIds, protectedTenantFileId, uniqueScopedProjectId} from '../../components/supply/SupplyTechnicalComparisonPanel';

export default function AccountingSupplierContracts(props) {
  const {companyContext = {}, user = {}} = props;
  const companyId = Number(companyContext.selectedCompanyId || companyContext.selectedCompany?.companyId);
  const role = companyContext.selectedCompany?.role || user.role;
  if (companyContext.loading || companyContext.mode === 'all_companies' || companyContext.selectedCompany?.readOnly
    || companyContext.selectedCompany?.active === false || !Number.isSafeInteger(companyId) || companyId <= 0
    || !['директор', 'зам_директора', 'бухгалтер'].includes(role)) return null;
  return <Workspace key={`${companyId}:${user.id}:${role}`} {...props} companyId={companyId}/>;
}

function Workspace({API, companyId, companyContext, user, suppliers = [], supplierOffers = [], supplyRequests = [], projects = [], C = {}}) {
  const [selectedId, setSelectedId] = useState('');
  const available = suppliers.filter(supplier => supplier.companyId === companyId && Number.isSafeInteger(supplier.id));
  const supplier = available.find(row => String(row.id) === selectedId);
  const canCheck = process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_ENABLED === 'true'
    && ['директор', 'зам_директора'].includes(companyContext.selectedCompany?.role)
    && (parseSupplyTechnicalComparisonCompanyIds(process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS) || new Set()).has(companyId);
  const offers = supplierOffers.filter(offer => offer.supplierId === supplier?.id
    && (offer.companyId == null || offer.companyId === companyId)
    && supplyRequests.some(request => request.id === offer.requestId && request.companyId === companyId));
  return <section aria-label="Договоры поставщиков" style={{padding:16, marginBottom:20, border:`1px solid ${C.border}`, borderRadius:12}}>
    <h3 style={{marginTop:0}}>Договоры поставщиков</h3>
    <p>Загрузите договор один раз. Он будет использоваться в следующих счетах этого поставщика.</p>
    <label>Поставщик<select value={supplier ? selectedId : ''} onChange={event => setSelectedId(event.target.value)} style={{display:'block',minHeight:44,width:'100%',margin:'8px 0 16px'}}>
      <option value="">Выберите поставщика</option>
      {available.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
    </select></label>
    {supplier && <SupplierContracts API={API} companyId={companyId} supplierId={supplier.id} userId={user.id}/>}
    {supplier && canCheck && offers.map(offer => {
      const request = supplyRequests.find(row => row.id === offer.requestId && row.companyId === companyId);
      const projectId = uniqueScopedProjectId(projects, request.project, companyId);
      const fileId = protectedTenantFileId(offer.pdfUrl);
      if (!projectId || !fileId) return null;
      return <details key={offer.id} style={{marginTop:12}}>
        <summary>Проверка предложения № {offer.id} · {request.project}</summary>
        <SupplyTechnicalComparisonPanel API={API} C={C} companyContext={companyContext} enabled={canCheck} allowedCompanyIds={new Set([companyId])}
          projectId={projectId} requestId={request.id}
          sourceKind="supplier_offer" sourceId={offer.id} fileId={fileId}/>
      </details>;
    })}
  </section>;
}
