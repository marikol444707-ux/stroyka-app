import { invoiceAmount } from '../../utils/accountingInvoices';
import { normalizeSupplierNameKey } from '../../utils/supplierUtils';

const LINK_REASONS = new Set([
  'accounting_supplier_warehouse_link_not_found',
  'accounting_supplier_warehouse_link_nonreciprocal',
]);

const positiveId = value => {
  const parsed = Number(value || 0);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
};

const companyIdOf = record => positiveId(record?.companyId || record?.company_id);
const warehouseSupplierInvoiceId = record => positiveId(
  record?.supplierInvoiceId || record?.supplier_invoice_id,
);
const supplierWarehouseInvoiceId = record => positiveId(
  record?.warehouseInvoiceId || record?.warehouse_invoice_id,
);
const warehouseProject = record => String(
  record?.project
  || (record?.location === 'Основной склад' ? '' : record?.location)
  || '',
).trim();
const supplierProject = record => String(
  record?.projectName || record?.project_name || '',
).trim();
const supplierIdOf = record => positiveId(record?.supplierId || record?.supplier_id);
const supplierNameOf = record => normalizeSupplierNameKey(
  record?.supplierName || record?.supplier_name || record?.supplier || '',
);
const supplierInvoiceAmount = record => Number(
  record?.amount || record?.totalAmount || record?.total_amount || 0,
);
const cents = value => (
  Number.isFinite(Number(value)) && Number(value) > 0
    ? Math.round(Number(value) * 100)
    : null
);

const sameSupplier = (warehouse, supplier) => {
  const warehouseSupplierId = supplierIdOf(warehouse);
  const supplierSupplierId = supplierIdOf(supplier);
  if (warehouseSupplierId && supplierSupplierId) {
    return warehouseSupplierId === supplierSupplierId;
  }
  const warehouseName = supplierNameOf(warehouse);
  const supplierName = supplierNameOf(supplier);
  return Boolean(warehouseName && supplierName && warehouseName === supplierName);
};

const exactDocumentMatch = ({
  companyId,
  expectedProject,
  supplier,
  warehouse,
}) => (
  companyIdOf(supplier) === companyId
  && companyIdOf(warehouse) === companyId
  && supplierProject(supplier) === expectedProject
  && warehouseProject(warehouse) === expectedProject
  && sameSupplier(warehouse, supplier)
  && cents(supplierInvoiceAmount(supplier)) === cents(invoiceAmount(warehouse))
  && String(supplier?.status || '') !== 'Аннулирован'
  && String(warehouse?.status || '') !== 'Аннулирована'
  && [null, positiveId(supplier?.id)].includes(warehouseSupplierInvoiceId(warehouse))
);

export const buildSafeAccountingLinkPlans = ({
  companyId,
  findings = [],
  invoices = [],
  projects = [],
  supplierInvoices = [],
} = {}) => {
  const selectedCompanyId = positiveId(companyId);
  if (!selectedCompanyId || !Array.isArray(findings)) {
    return { plans: [], unresolvedCount: Array.isArray(findings) ? findings.length : 0 };
  }

  const projectById = new Map(
    (projects || [])
      .filter(project => companyIdOf(project) === selectedCompanyId)
      .map(project => [positiveId(project?.id), String(project?.name || '').trim()]),
  );
  const supplierById = new Map(
    (supplierInvoices || []).map(invoice => [positiveId(invoice?.id), invoice]),
  );
  const warehouseById = new Map(
    (invoices || []).map(invoice => [positiveId(invoice?.id), invoice]),
  );
  const plansByPair = new Map();
  const resolvedFindings = new Set();

  findings.forEach((finding, index) => {
    if (!LINK_REASONS.has(finding?.reasonCode)) return;
    const expectedProject = projectById.get(positiveId(finding?.projectId));
    if (!expectedProject) return;

    let supplier = null;
    let warehouse = null;
    let candidates = [];
    if (finding.subjectKind === 'supplier_invoice') {
      supplier = supplierById.get(positiveId(finding.subjectId));
      if (!supplier) return;
      const directWarehouse = finding.reasonCode.endsWith('_nonreciprocal')
        ? warehouseById.get(positiveId(finding.relatedId))
        : null;
      candidates = directWarehouse ? [directWarehouse] : [...warehouseById.values()];
      candidates = candidates.filter(candidate => exactDocumentMatch({
        companyId: selectedCompanyId,
        expectedProject,
        supplier,
        warehouse: candidate,
      }));
      if (supplierWarehouseInvoiceId(supplier) !== positiveId(finding.relatedId)) return;
      if (candidates.length === 1) [warehouse] = candidates;
    } else if (finding.subjectKind === 'warehouse_invoice') {
      warehouse = warehouseById.get(positiveId(finding.subjectId));
      if (!warehouse) return;
      const directSupplier = finding.reasonCode.endsWith('_nonreciprocal')
        ? supplierById.get(positiveId(finding.relatedId))
        : null;
      candidates = directSupplier ? [directSupplier] : [...supplierById.values()];
      candidates = candidates.filter(candidate => exactDocumentMatch({
        companyId: selectedCompanyId,
        expectedProject,
        supplier: candidate,
        warehouse,
      }));
      if (warehouseSupplierInvoiceId(warehouse) !== positiveId(finding.relatedId)
          && finding.reasonCode.endsWith('_not_found')) return;
      if (candidates.length === 1) [supplier] = candidates;
    }

    const supplierInvoiceId = positiveId(supplier?.id);
    const warehouseInvoiceId = positiveId(warehouse?.id);
    if (!supplierInvoiceId || !warehouseInvoiceId) return;
    const pairKey = `${supplierInvoiceId}:${warehouseInvoiceId}`;
    plansByPair.set(pairKey, { supplierInvoiceId, warehouseInvoiceId });
    resolvedFindings.add(index);
  });

  return {
    plans: [...plansByPair.values()],
    unresolvedCount: findings.length - resolvedFindings.size,
  };
};
