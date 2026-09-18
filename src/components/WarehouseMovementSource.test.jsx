import React from 'react';
import { render, screen } from '@testing-library/react';
import WarehouseMovementSource from './WarehouseMovementSource';

const movement = { companyId: 2, sourceInvoiceId: 10, sourceInvoiceLineIndex: 0 };
const invoice = { id: 10, companyId: 2, number: 'НК-20', supplierName: 'Поставщик А', items: [{ name: 'Кабель', invoiceLineIndex: 0 }] };
const show = (changes = {}, invoices = [invoice]) => render(<WarehouseMovementSource movement={{ ...movement, ...changes }} invoices={invoices} />);

test('finds original line 2 when it is the only visible item', () => {
  show({ sourceInvoiceLineIndex: 2 }, [{ ...invoice, items: [{ invoiceLineIndex: 2 }] }]);
  expect(screen.getByText(/НК-20/)).toHaveTextContent('строка 3');
});

test.each([
  [{ invoiceLineIndex: 2 }], [{}], [{ invoiceLineIndex: null }],
  [{ invoiceLineIndex: '0' }], [{ invoiceLineIndex: true }],
  [{ invoiceLineIndex: -1 }], [{ invoiceLineIndex: 0.5 }],
  [{ invoiceLineIndex: Number.MAX_SAFE_INTEGER + 1 }],
  [{ invoiceLineIndex: 0 }, { invoiceLineIndex: 0 }],
].map(items => [items]))('does not infer hidden or unidentified source line from array position %#', items => {
  show({}, [{ ...invoice, items }]);
  expect(screen.getByText(/требует проверки/)).toBeInTheDocument();
  expect(screen.queryByText('Поставщик А')).not.toBeInTheDocument();
});

test('shows only the exact same-company stored receipt and its one-based line', () => {
  show();
  expect(screen.getByText(/НК-20/)).toHaveTextContent('строка 1');
  expect(screen.getByText('Поставщик А')).toBeInTheDocument();
});

test('legacy movement without source stays unlinked even with a matching receipt name', () => {
  show({ sourceInvoiceId: null, sourceInvoiceLineIndex: null, materialName: 'Кабель' });
  expect(screen.getByText('Источник поступления не указан')).toBeInTheDocument();
  expect(screen.queryByText('Поставщик А')).not.toBeInTheDocument();
});

test.each([
  [{ companyId: null }, [invoice]],
  [{ companyId: 3 }, [invoice]],
  [{ sourceInvoiceId: 99 }, [invoice]],
  [{ sourceInvoiceLineIndex: null }, [invoice]],
  [{ sourceInvoiceLineIndex: true }, [invoice]],
  [{ sourceInvoiceLineIndex: -1 }, [invoice]],
  [{ sourceInvoiceLineIndex: 1 }, [invoice]],
  [{}, [invoice, invoice]],
  [{}, [{ ...invoice, status: 'Аннулирована' }]],
])('does not guess or disclose receipt metadata for inconsistent source %#', (changes, invoices) => {
  show(changes, invoices);
  expect(screen.getByText(/Источник поступления требует проверки/)).toBeInTheDocument();
  expect(screen.queryByText(/НК-20/)).not.toBeInTheDocument();
  expect(screen.queryByText('Поставщик А')).not.toBeInTheDocument();
});

test('does not expose invoice debt or payment deadline in warehouse history', () => {
  show({}, [{ ...invoice, totalWithVat: 9000, paidAmount: 100, paymentDeadline: { status: 'active' } }]);
  expect(screen.queryByText(/9000|8900|Отсрочка/)).not.toBeInTheDocument();
});
