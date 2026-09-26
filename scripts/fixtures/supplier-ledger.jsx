import React from 'react';
import { createRoot } from 'react-dom/client';
import SupplierPaymentDialog from '../../src/features/supplier-payments/SupplierPaymentDialog';
import LedgerAccountingPreview from './supplier-ledger-accounting';

function Preview() {
  const [open, setOpen] = React.useState(false);
  const [companyId, setCompanyId] = React.useState(2);
  const [successes, setSuccesses] = React.useState(0);
  return <main style={{ padding: 24, fontFamily: 'sans-serif' }}>
    <h1>Тестовый журнал оплат</h1>
    <p>Только вымышленные данные. Компания 3 намеренно теряет первый ответ после записи платежа.</p>
    <label>Компания <select value={companyId} onChange={event => setCompanyId(Number(event.target.value))}>
      <option value={2}>Компания 2 — обычный ответ</option>
      <option value={3}>Компания 3 — потеря ответа</option>
      <option value={4}>Компания 4 — отказ, затем отмена попытки</option>
    </select></label>
    <p><button onClick={() => setOpen(true)}>Открыть оплату</button></p>
    <p role="status">Подтверждённых действий в этой вкладке: {successes}</p>
    <SupplierPaymentDialog enabled open={open} API="/synthetic-api" userId={4} companyId={companyId}
      documentKind="invoice" documentId={9} onClose={() => setOpen(false)}
      onSuccess={() => setSuccesses(value => value + 1)} />
  </main>;
}
createRoot(document.getElementById('root')).render(new URLSearchParams(window.location.search).has('accounting')
  ? <LedgerAccountingPreview /> : <Preview />);
