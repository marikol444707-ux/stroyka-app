import { buildSafeAccountingLinkPlans } from './accountingExceptionRemediation';

const finding = (overrides = {}) => ({
  reasonCode: 'accounting_supplier_warehouse_link_not_found',
  subjectKind: 'supplier_invoice',
  subjectId: 91,
  projectId: 17,
  relatedId: 999,
  ...overrides,
});

const supplierInvoice = (overrides = {}) => ({
  id: 91,
  companyId: 4,
  projectName: 'ЖК Северный',
  supplierId: 12,
  supplierName: 'ООО Поставка',
  amount: 1000,
  warehouseInvoiceId: 999,
  status: 'На утверждении',
  ...overrides,
});

const warehouseInvoice = (overrides = {}) => ({
  id: 44,
  companyId: 4,
  project: 'ЖК Северный',
  supplierId: 12,
  supplierName: 'ООО Поставка',
  totalWithVat: 1000,
  supplierInvoiceId: null,
  status: 'Принята',
  ...overrides,
});

const input = (overrides = {}) => ({
  companyId: 4,
  findings: [finding()],
  invoices: [warehouseInvoice()],
  projects: [{ id: 17, companyId: 4, name: 'ЖК Северный' }],
  supplierInvoices: [supplierInvoice()],
  ...overrides,
});

describe('buildSafeAccountingLinkPlans', () => {
  test('selects one exact company, project, supplier and amount match', () => {
    expect(buildSafeAccountingLinkPlans(input())).toEqual({
      plans: [{
        supplierInvoiceId: 91,
        warehouseInvoiceId: 44,
      }],
      unresolvedCount: 0,
    });
  });

  test('refuses to guess when more than one warehouse document matches', () => {
    const result = buildSafeAccountingLinkPlans(input({
      invoices: [warehouseInvoice(), warehouseInvoice({ id: 45 })],
    }));

    expect(result).toEqual({ plans: [], unresolvedCount: 1 });
  });

  test('refuses cross-company, different-project, different-supplier and amount matches', () => {
    const unsafeCandidates = [
      warehouseInvoice({ id: 45, companyId: 5 }),
      warehouseInvoice({ id: 46, project: 'Другой объект' }),
      warehouseInvoice({ id: 47, supplierId: 13 }),
      warehouseInvoice({ id: 48, totalWithVat: 1000.01 }),
      warehouseInvoice({ id: 49, supplierInvoiceId: 777 }),
    ];

    expect(buildSafeAccountingLinkPlans(input({ invoices: unsafeCandidates })))
      .toEqual({ plans: [], unresolvedCount: 1 });
  });

  test('deduplicates reciprocal findings for the same document pair', () => {
    const result = buildSafeAccountingLinkPlans(input({
      findings: [
        finding({
          reasonCode: 'accounting_supplier_warehouse_link_nonreciprocal',
          relatedId: 44,
        }),
        finding({
          reasonCode: 'accounting_supplier_warehouse_link_nonreciprocal',
          subjectKind: 'warehouse_invoice',
          subjectId: 44,
          relatedId: 91,
        }),
      ],
      supplierInvoices: [supplierInvoice({ warehouseInvoiceId: 44 })],
      invoices: [warehouseInvoice({ supplierInvoiceId: null })],
    }));

    expect(result).toEqual({
      plans: [{ supplierInvoiceId: 91, warehouseInvoiceId: 44 }],
      unresolvedCount: 0,
    });
  });
});
