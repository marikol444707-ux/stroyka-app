import React from 'react';
import { identifiedInvoiceLines, isInvoiceLineIndex } from '../utils/warehouseInvoiceSource';

const integer = value => /^\d+$/.test(String(value)) && Number.isSafeInteger(Number(value));
const positive = value => integer(value) && Number(value) > 0;

// Display only the persisted source; names and current company are never links.
export default function WarehouseMovementSource({ movement, invoices = [], C = {} }) {
  const sourceId = movement.sourceInvoiceId;
  const line = movement.sourceInvoiceLineIndex;
  const companyId = movement.companyId;
  const style = { fontSize: '12px', color: C.textSec, overflowWrap: 'anywhere', marginTop: '6px' };
  if (sourceId == null && line == null) return <div style={style}>Источник поступления не указан</div>;
  const matches = positive(sourceId) && positive(companyId)
    ? invoices.filter(invoice => positive(invoice.id) && Number(invoice.id) === Number(sourceId)
      && positive(invoice.companyId) && Number(invoice.companyId) === Number(companyId)) : [];
  const invoice = matches.length === 1 ? matches[0] : null;
  if (!invoice || !isInvoiceLineIndex(line)
    || !identifiedInvoiceLines(invoice.items).some(item => item.invoiceLineIndex === line)
    || invoice.status === 'Аннулирована') {
    return <div style={{ ...style, color: C.warning }}>Источник поступления требует проверки или недоступен</div>;
  }
  return <div style={style}>
    <div>Исходная накладная № {invoice.number || invoice.id} · строка {Number(line) + 1}</div>
    {invoice.supplierName && <div>{invoice.supplierName}</div>}
  </div>;
}
