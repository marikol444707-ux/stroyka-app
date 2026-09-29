import React, { useEffect, useState } from 'react';
import { API } from '../../api';
import SupplierPaymentDialog from './SupplierPaymentDialog';

export default function SupplierPaymentButton({ document, documentKind, companyContext = {}, user,
  onSuccess, disabled = false, style }) {
  const [openedScope, setOpenedScope] = useState(null);
  const companyId = Number(companyContext.selectedCompanyId);
  const documentId = Number(document?.id);
  const ownerId = Number(document?.companyId ?? document?.company_id);
  const userId = Number(user?.id);
  const ready = companyContext.mode === 'company' && !companyContext.loading && !companyContext.error
    && [companyId, documentId, userId].every(id => Number.isSafeInteger(id) && id > 0)
    && companyId === ownerId;
  const scope = JSON.stringify([companyContext.mode, companyId, userId, documentKind, documentId]);
  useEffect(() => setOpenedScope(null), [scope, ready]);
  if (process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED !== 'true') return null;
  return <>
    <button type="button" style={style} disabled={disabled || !ready}
      title={!ready ? 'Выберите компанию этого документа' : undefined}
      onClick={() => setOpenedScope(scope)}>Оплата и история</button>
    {ready && openedScope === scope && <SupplierPaymentDialog API={API} userId={userId}
      companyId={companyId} documentKind={documentKind} documentId={documentId}
      onSuccess={onSuccess} onClose={() => setOpenedScope(null)} />}
  </>;
}
