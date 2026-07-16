export const emptySupplierForm = () => ({
  name: '',
  phone: '',
  email: '',
  specialization: '',
  category: 'Сыпучие и бетон',
  rating: 5.0,
  status: 'Активный',
  inn: '',
  kpp: '',
  ogrn: '',
  legalAddress: '',
  actualAddress: '',
  bank: '',
  bik: '',
  account: '',
  korAccount: '',
  directorName: '',
  directorPosition: '',
  contractUrl: '',
  contractNumber: '',
  contractDate: '',
  licenseUrl: '',
  priceUrl: '',
  website: '',
  notes: '',
  sourceType: 'manual',
  sourceDetail: '',
});

export const normalizeSupplierPayload = (supplier = {}) => ({
  ...emptySupplierForm(),
  ...supplier,
  legalAddress: supplier.legalAddress || supplier.legal_address || '',
  actualAddress: supplier.actualAddress || supplier.actual_address || '',
  korAccount: supplier.korAccount || supplier.kor_account || '',
  directorName: supplier.directorName || supplier.director_name || '',
  directorPosition: supplier.directorPosition || supplier.director_position || '',
  contractUrl: supplier.contractUrl || supplier.contract_url || '',
  contractNumber: supplier.contractNumber || supplier.contract_number || '',
  contractDate: String(supplier.contractDate || supplier.contract_date || '').slice(0, 10),
  licenseUrl: supplier.licenseUrl || supplier.license_url || '',
  priceUrl: supplier.priceUrl || supplier.price_url || '',
  sourceType: supplier.sourceType || supplier.source_type || 'manual',
  sourceDetail: supplier.sourceDetail || supplier.source_detail || '',
});

export const normalizeSupplierNameKey = value => String(value || '')
  .toLowerCase()
  .replace(/ё/g, 'е')
  .replace(/(?:,|\s)\s*(инн|кпп|огрн|огрнип|тел\.?|телефон|р\/с|расч[её]тн|адрес)(?=$|[^а-яa-z]).*$/g, ' ')
  .replace(/(^|[^а-яa-z])(инн|кпп|огрн|огрнип)\s*[:№#-]?\s*\d+(?=$|[^а-яa-z])/g, ' ')
  .replace(/\b(ооо|оао|ао|пао|зао|ип|индивидуальный предприниматель)\b/g, ' ')
  .replace(/[.,;:()«»"'`/\\]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

export const normalizeSupplierDigits = value => String(value || '').replace(/\D/g, '');

export const normalizeSupplierEmail = value => String(value || '').trim().toLowerCase();

export const normalizeSupplierRecordName = value => String(value || '')
  .toLowerCase()
  .replace(/ё/g, 'е')
  .replace(/[.,;:()«»"'`/\\]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

export const supplierKeysMatch = (left, right) => {
  if (!left || !right) return false;
  if (left === right) return true;
  const short = left.length < right.length ? left : right;
  const long = left.length < right.length ? right : left;
  return short.length >= 6 && long.includes(short);
};

const supplierNameNoiseTokens = new Set([
  'ооо', 'оао', 'ао', 'пао', 'зао', 'ип',
  'из', 'по', 'для', 'накладной', 'накладная', 'счет', 'счета',
]);

const supplierNameTokens = value => (
  normalizeSupplierNameKey(value)
    .split(' ')
    .filter(token => token.length >= 1 && !supplierNameNoiseTokens.has(token))
);

const supplierPersonInitialMatch = (leftTokens, rightTokens) => {
  const hasInitials = leftTokens.length >= 3 && leftTokens[1]?.length === 1 && leftTokens[2]?.length === 1;
  const hasFullName = rightTokens.length >= 3 && rightTokens[1]?.length > 1 && rightTokens[2]?.length > 1;
  if (!hasInitials || !hasFullName) return false;
  return (
    leftTokens[0] === rightTokens[0]
    && rightTokens[1].startsWith(leftTokens[1])
    && rightTokens[2].startsWith(leftTokens[2])
  );
};

export const supplierNameDuplicateReason = (left, right) => {
  const leftTokens = supplierNameTokens(left?.name || left?.supplierName || left?.supplier_name || left?.supplier || '');
  const rightTokens = supplierNameTokens(right?.name || right?.supplierName || right?.supplier_name || right?.supplier || '');
  const leftNameTokens = leftTokens.filter(token => token.length >= 2);
  const rightNameTokens = rightTokens.filter(token => token.length >= 2);
  const leftKey = leftNameTokens.join(' ');
  const rightKey = rightNameTokens.join(' ');
  if (!leftKey || !rightKey) return '';
  if (leftKey === rightKey) return 'совпадает название';
  if (supplierPersonInitialMatch(leftTokens, rightTokens) || supplierPersonInitialMatch(rightTokens, leftTokens)) return 'похожее ФИО';
  if (supplierKeysMatch(leftKey, rightKey)) return 'похожее название';
  const leftSet = new Set(leftTokens);
  const rightSet = new Set(rightTokens);
  const common = [...leftSet].filter(token => rightSet.has(token));
  if (common.length >= 2 && common.length >= Math.min(leftSet.size, rightSet.size, 3)) {
    return 'похожее название';
  }
  return '';
};

export const supplierIdentityKeys = supplier => {
  const inn = normalizeSupplierDigits(supplier?.inn || supplier?.supplierInn || supplier?.supplier_inn);
  const ogrn = normalizeSupplierDigits(supplier?.ogrn || supplier?.supplierOgrn || supplier?.supplier_ogrn);
  const email = normalizeSupplierEmail(supplier?.email || supplier?.supplierEmail || supplier?.supplier_email);
  const phone = normalizeSupplierDigits(supplier?.phone || supplier?.supplierPhone || supplier?.supplier_phone);
  return [
    inn.length >= 10 ? 'inn:' + inn : '',
    ogrn.length >= 13 ? 'ogrn:' + ogrn : '',
    email && email.includes('@') ? 'email:' + email : '',
    phone.length >= 7 ? 'phone:' + phone : '',
  ].filter(Boolean);
};

export const SUPPLIER_SOURCE_META = {
  manual: { label: 'Вручную', color: '#64748b' },
  invite_link: { label: 'По ссылке', color: '#2563eb' },
  linked_account: { label: 'Связан вручную', color: '#7c3aed' },
  warehouse_invoice: { label: 'Из накладной', color: '#0f766e' },
  max_invoice: { label: 'MAX-накладная', color: '#0891b2' },
  site: { label: 'С сайта', color: '#ea580c' },
  crm: { label: 'CRM', color: '#f97316' },
  other: { label: 'Другой источник', color: '#475569' },
};

export const SOURCE_FILTERS = [
  { id: 'all', label: 'Все' },
  { id: 'needs_review', label: 'Проверка' },
  { id: 'invite_link', label: 'Ссылка' },
  { id: 'site', label: 'Сайт/CRM' },
  { id: 'warehouse_invoice', label: 'Накладная' },
  { id: 'manual', label: 'Вручную' },
  { id: 'linked_account', label: 'Связанные' },
];

export const sourceMeta = type => SUPPLIER_SOURCE_META[type] || SUPPLIER_SOURCE_META.other;

export const supplierHasStrongIdentity = supplier => (
  (supplier?._supplierIdentityKeys || supplierIdentityKeys(supplier)).length > 0
);

export const supplierMatchesRecord = (supplier, record) => {
  const ids = new Set((supplier?._supplierIds || [supplier?.id]).map(id => Number(id)).filter(Boolean));
  const recordId = Number(record?.supplierId || record?.supplier_id || 0);
  if (recordId && ids.has(recordId)) return true;
  const recordName = normalizeSupplierRecordName(record?.supplierName || record?.supplier_name || record?.supplier || '');
  return Boolean(recordName && (supplier?._supplierRecordNames || []).includes(recordName));
};

export const supplierSourceInfo = (supplier, stats = {}) => {
  const rawTypes = [
    supplier?.sourceType,
    supplier?.source_type,
    ...(supplier?._supplierSourceTypes || []),
  ].filter(Boolean);
  const types = Array.from(new Set(rawTypes));
  const hasLinkedAccount = supplier?.userId || supplier?.user_id || supplier?.registeredAt || supplier?.registered_at;
  if (hasLinkedAccount && !types.includes('invite_link') && !types.includes('linked_account')) {
    types.push('invite_link');
  }
  if ((stats.warehouseInvoices || []).length > 0 && !types.includes('warehouse_invoice')) {
    types.push('warehouse_invoice');
  }
  if (!types.length) types.push('manual');
  const sourcePriority = ['warehouse_invoice', 'max_invoice', 'invite_link', 'site', 'crm', 'linked_account', 'manual'];
  const primary = sourcePriority.find(type => types.includes(type)) || types[0];
  const filterTypes = types.flatMap(type => type === 'crm' ? ['crm', 'site'] : [type]);
  const details = [
    supplier?.sourceDetail,
    supplier?.source_detail,
    ...(supplier?._supplierSourceDetails || []),
  ].filter(Boolean);
  return {
    primary,
    types,
    filterTypes,
    label: sourceMeta(primary).label,
    detail: details[0] || '',
  };
};

export const supplierReviewInfo = (supplier, stats = {}, possibleDuplicates = []) => {
  const sourceInfo = supplierSourceInfo(supplier, stats);
  const reasons = [];
  const status = String(supplier?.status || '').trim().toLowerCase();
  const fromInvoice = sourceInfo.types.some(type => ['warehouse_invoice', 'max_invoice'].includes(type));
  const linkedAccount = Boolean(supplier?.userId || supplier?.user_id || supplier?.registeredAt || supplier?.registered_at);

  if (status === 'нужно уточнение') {
    reasons.push('карточка в статусе "Нужно уточнение"');
  }
  if (fromInvoice && !supplierHasStrongIdentity(supplier)) {
    reasons.push('создан из накладной без ИНН/ОГРН/email/телефона');
  }
  if (fromInvoice && !linkedAccount && !supplierHasStrongIdentity(supplier)) {
    reasons.push('нет живого кабинета поставщика');
  }
  if ((possibleDuplicates || []).length > 0) {
    reasons.push('есть похожие карточки');
  }
  if (Number(supplier?._duplicateCount || 0) > 1) {
    reasons.push('есть объединённые дубли карточек');
  }
  if (Number(stats?.duplicateDocumentsCount || 0) > 0) {
    reasons.push('есть скрытые дубли документов');
  }

  return {
    needsReview: reasons.length > 0,
    reasons,
    label: reasons[0] || '',
  };
};

const supplierDocumentNumberKey = value => String(value || '')
  .toLowerCase()
  .replace(/\s+/g, '')
  .trim();

const supplierDocumentTextKey = value => String(value || '')
  .toLowerCase()
  .replace(/ё/g, 'е')
  .replace(/\s+/g, ' ')
  .trim();

const supplierDocumentNumber = value => {
  const num = Number(String(value || 0).replace(/\s+/g, '').replace(',', '.'));
  return Number.isFinite(num) ? num : 0;
};

const supplierDocumentItemName = item => item?.materialName || item?.material_name || item?.name || '';

const supplierDocumentItemTotal = item => {
  const line = supplierDocumentNumber(item?.lineTotal || item?.line_total);
  return line > 0
    ? line
    : supplierDocumentNumber(item?.quantity) * supplierDocumentNumber(item?.price || item?.pricePerUnit || item?.price_per_unit);
};

const supplierDocumentItemsTotal = invoice => (invoice?.items || []).reduce((sum, item) => sum + supplierDocumentItemTotal(item), 0);

const supplierDocumentItemSignature = item => [
  supplierDocumentTextKey(supplierDocumentItemName(item)),
  supplierDocumentTextKey(item?.unit || item?.unitName || item?.unit_name),
  supplierDocumentNumber(item?.quantity).toFixed(4),
  supplierDocumentNumber(item?.price || item?.pricePerUnit || item?.price_per_unit).toFixed(2),
  supplierDocumentItemTotal(item).toFixed(2),
].join('|');

export const supplierDocumentItemsSignature = items => (items || [])
  .map(supplierDocumentItemSignature)
  .filter(Boolean)
  .sort()
  .join('||');

export const warehouseInvoiceDocumentKey = invoice => {
  const number = supplierDocumentNumberKey(invoice?.number || invoice?.invoiceNumber || invoice?.invoice_number);
  const date = String(invoice?.date || invoice?.invoiceDate || invoice?.createdAt || '').slice(0, 10);
  const supplier = normalizeSupplierNameKey(invoice?.supplierName || invoice?.supplier_name || invoice?.supplier || '');
  const place = supplierDocumentTextKey(invoice?.project || invoice?.location || invoice?.warehouseTarget || '');
  const totalValue = supplierDocumentNumber(invoice?.totalWithVat || invoice?.total_with_vat) || supplierDocumentItemsTotal(invoice);
  const total = totalValue.toFixed(2);
  const itemKey = supplierDocumentItemsSignature(invoice?.items || []);
  if (number && (totalValue > 0 || itemKey)) return ['warehouse-number', number, date, place, total, itemKey].join('|');
  if (number) return ['warehouse-number-supplier', number, date, supplier, place].join('|');
  if (date && supplier && itemKey) return ['warehouse-content', date, supplier, place, total, itemKey].join('|');
  return invoice?.id ? 'warehouse-id:' + invoice.id : '';
};

export const groupSuppliers = suppliers => {
  const groups = new Map();
  const keyIndex = new Map();

  const relationInfo = supplier => {
    const explicitIds = supplier?.relatedSupplierIds || supplier?.related_supplier_ids || [];
    const explicitCanonicalId = Number(
      supplier?.canonicalSupplierId || supplier?.canonical_supplier_id || 0
    );
    const ids = Array.from(new Set([
      ...explicitIds,
      supplier?.id,
    ].map(id => Number(id)).filter(Boolean))).sort((a, b) => a - b);
    const canonicalId = Number(
      explicitCanonicalId
      || (ids.length > 1 ? ids[0] : supplier?.id)
      || 0
    );
    return {
      ids,
      canonicalId,
      explicit: (explicitIds.length > 0 || explicitCanonicalId > 0) && ids.length > 1,
    };
  };

  const orderedSuppliers = [...(suppliers || [])].sort((left, right) => {
    const leftRelation = relationInfo(left);
    const rightRelation = relationInfo(right);
    const leftCanonical = Number(left?.id) === leftRelation.canonicalId ? 0 : 1;
    const rightCanonical = Number(right?.id) === rightRelation.canonicalId ? 0 : 1;
    return leftCanonical - rightCanonical;
  });

  orderedSuppliers.forEach(supplier => {
    const identityKeys = supplierIdentityKeys(supplier);
    const nameKey = normalizeSupplierNameKey(supplier?.name || supplier?.supplierName || '');
    const fallbackKey = supplier?.id ? 'id:' + supplier.id : 'row:' + groups.size;
    const relation = relationInfo(supplier);
    const relationKey = relation.ids.length > 1 ? 'relation:' + relation.canonicalId : '';
    const existingRelationKey = relationKey ? keyIndex.get(relationKey) : '';
    const identityMatch = identityKeys.find(key => keyIndex.has(key));
    const existingIdentityKey = identityMatch ? keyIndex.get(identityMatch) : '';
    const groupKey = existingRelationKey || existingIdentityKey || relationKey || identityKeys[0] || fallbackKey;

    if (!groups.has(groupKey)) {
      const sourceType = supplier.sourceType || supplier.source_type || '';
      const sourceDetail = supplier.sourceDetail || supplier.source_detail || '';
      groups.set(groupKey, {
        ...supplier,
        sourceType,
        sourceDetail,
        alreadyRequested: Boolean(supplier.alreadyRequested),
        aiRecommend: Boolean(supplier.aiRecommend),
        deliveriesCount: Number(supplier.deliveriesCount || 0),
        category: supplier.category || 'Прочее',
        _supplierIds: relation.ids.length ? relation.ids : [supplier.id],
        _supplierKeys: nameKey ? [nameKey] : [],
        _supplierNames: [supplier.name || supplier.supplierName || ''],
        _supplierRecordNames: [normalizeSupplierRecordName(supplier.name || supplier.supplierName || '')].filter(Boolean),
        _supplierIdentityKeys: [...identityKeys],
        _supplierSourceTypes: sourceType ? [sourceType] : [],
        _supplierSourceDetails: sourceDetail ? [sourceDetail] : [],
        _canonicalSupplierId: relation.explicit ? relation.canonicalId : 0,
        _duplicateCount: relation.ids.length || 1,
      });
      if (relationKey) keyIndex.set(relationKey, groupKey);
      identityKeys.forEach(key => keyIndex.set(key, groupKey));
      return;
    }

    const group = groups.get(groupKey);
    if (relationKey) keyIndex.set(relationKey, groupKey);
    const isServerCanonical = relation.explicit && Number(supplier.id) === relation.canonicalId;
    if (isServerCanonical && Number(group.id) !== Number(supplier.id)) {
      group.id = supplier.id;
      group.name = supplier.name || group.name;
      group.phone = supplier.phone || group.phone;
      group.email = supplier.email || group.email;
      group.inn = supplier.inn || group.inn;
      group.kpp = supplier.kpp || group.kpp;
      group.ogrn = supplier.ogrn || group.ogrn;
    }
    group._supplierIds = Array.from(new Set([
      ...group._supplierIds,
      ...relation.ids,
      supplier.id,
    ].map(id => Number(id)).filter(Boolean))).sort((a, b) => a - b);
    group._supplierNames.push(supplier.name || supplier.supplierName || '');
    const supplierRecordName = normalizeSupplierRecordName(supplier.name || supplier.supplierName || '');
    if (supplierRecordName && !group._supplierRecordNames.includes(supplierRecordName)) {
      group._supplierRecordNames.push(supplierRecordName);
    }
    group._duplicateCount = group._supplierIds.length;
    const sourceType = supplier.sourceType || supplier.source_type || '';
    const sourceDetail = supplier.sourceDetail || supplier.source_detail || '';
    if (sourceType && !group._supplierSourceTypes.includes(sourceType)) group._supplierSourceTypes.push(sourceType);
    if (sourceDetail && !group._supplierSourceDetails.includes(sourceDetail)) group._supplierSourceDetails.push(sourceDetail);
    if (nameKey && !group._supplierKeys.includes(nameKey)) group._supplierKeys.push(nameKey);
    identityKeys.forEach(key => {
      if (!group._supplierIdentityKeys.includes(key)) group._supplierIdentityKeys.push(key);
      keyIndex.set(key, groupKey);
    });

    if (!group._canonicalSupplierId && relation.explicit && relation.canonicalId) {
      group._canonicalSupplierId = relation.canonicalId;
    }
    if (
      !group._canonicalSupplierId
      && (!group.name || String(supplier.name || '').length > String(group.name || '').length)
    ) group.name = supplier.name;
    if (!group.phone && supplier.phone) group.phone = supplier.phone;
    if (!group.email && supplier.email) group.email = supplier.email;
    if (!group.inn && supplier.inn) group.inn = supplier.inn;
    if (!group.kpp && supplier.kpp) group.kpp = supplier.kpp;
    if (!group.ogrn && supplier.ogrn) group.ogrn = supplier.ogrn;
    if (!group.specialization && supplier.specialization) group.specialization = supplier.specialization;
    if ((!group.category || group.category === 'Прочее') && supplier.category) group.category = supplier.category;
    if (!group.status && supplier.status) group.status = supplier.status;
    if (!group.sourceType && sourceType) group.sourceType = sourceType;
    if (!group.sourceDetail && sourceDetail) group.sourceDetail = sourceDetail;
    group.rating = Math.max(Number(group.rating || 0), Number(supplier.rating || 0));
    group.deliveriesCount = Math.max(Number(group.deliveriesCount || 0), Number(supplier.deliveriesCount || 0));
    group.alreadyRequested = Boolean(group.alreadyRequested || supplier.alreadyRequested);
    group.aiRecommend = Boolean(group.aiRecommend || supplier.aiRecommend);
  });

  return Array.from(groups.values()).sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'ru'));
};
