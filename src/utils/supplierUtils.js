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
  .replace(/(?:,|\s)\s*(инн|кпп|огрн|огрнип|тел\.?|телефон|р\/с|расч[её]тн|адрес)\b.*$/g, ' ')
  .replace(/\b(инн|кпп|огрн|огрнип)\s*[:№#-]?\s*\d+\b/g, ' ')
  .replace(/\b(ооо|оао|ао|пао|зао|ип|индивидуальный предприниматель)\b/g, ' ')
  .replace(/[.,;:()«»"'`/\\]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

export const normalizeSupplierDigits = value => String(value || '').replace(/\D/g, '');

export const normalizeSupplierEmail = value => String(value || '').trim().toLowerCase();

export const supplierKeysMatch = (left, right) => {
  if (!left || !right) return false;
  if (left === right) return true;
  const short = left.length < right.length ? left : right;
  const long = left.length < right.length ? right : left;
  return short.length >= 6 && long.includes(short);
};

export const supplierIdentityKeys = supplier => {
  const inn = normalizeSupplierDigits(supplier?.inn || supplier?.supplierInn || supplier?.supplier_inn);
  const ogrn = normalizeSupplierDigits(supplier?.ogrn || supplier?.supplierOgrn || supplier?.supplier_ogrn);
  const email = normalizeSupplierEmail(supplier?.email || supplier?.supplierEmail || supplier?.supplier_email);
  const phone = normalizeSupplierDigits(supplier?.phone || supplier?.supplierPhone || supplier?.supplier_phone);
  const nameKey = normalizeSupplierNameKey(
    supplier?.name || supplier?.supplierName || supplier?.supplier_name || supplier?.supplier || ''
  );
  return [
    inn.length >= 10 ? 'inn:' + inn : '',
    ogrn.length >= 13 ? 'ogrn:' + ogrn : '',
    email && email.includes('@') ? 'email:' + email : '',
    phone.length >= 7 ? 'phone:' + phone : '',
    nameKey ? 'name:' + nameKey : '',
  ].filter(Boolean);
};

export const groupSuppliers = suppliers => {
  const groups = new Map();
  const keyIndex = new Map();

  (suppliers || []).forEach(supplier => {
    const identityKeys = supplierIdentityKeys(supplier);
    const nameKey = normalizeSupplierNameKey(supplier?.name || supplier?.supplierName || '');
    const fallbackKey = supplier?.id ? 'id:' + supplier.id : 'row:' + groups.size;
    const matchedKey = identityKeys.find(key => keyIndex.has(key));
    const groupKey = matchedKey ? keyIndex.get(matchedKey) : (identityKeys[0] || fallbackKey);

    if (!groups.has(groupKey)) {
      const sourceType = supplier.sourceType || supplier.source_type || '';
      const sourceDetail = supplier.sourceDetail || supplier.source_detail || '';
      groups.set(groupKey, {
        ...supplier,
        sourceType,
        sourceDetail,
        category: supplier.category || 'Прочее',
        _supplierIds: [supplier.id],
        _supplierKeys: nameKey ? [nameKey] : [],
        _supplierNames: [supplier.name || supplier.supplierName || ''],
        _supplierIdentityKeys: [...identityKeys],
        _supplierSourceTypes: sourceType ? [sourceType] : [],
        _supplierSourceDetails: sourceDetail ? [sourceDetail] : [],
        _duplicateCount: 1,
      });
      identityKeys.forEach(key => keyIndex.set(key, groupKey));
      return;
    }

    const group = groups.get(groupKey);
    group._supplierIds.push(supplier.id);
    group._supplierNames.push(supplier.name || supplier.supplierName || '');
    group._duplicateCount += 1;
    const sourceType = supplier.sourceType || supplier.source_type || '';
    const sourceDetail = supplier.sourceDetail || supplier.source_detail || '';
    if (sourceType && !group._supplierSourceTypes.includes(sourceType)) group._supplierSourceTypes.push(sourceType);
    if (sourceDetail && !group._supplierSourceDetails.includes(sourceDetail)) group._supplierSourceDetails.push(sourceDetail);
    if (nameKey && !group._supplierKeys.includes(nameKey)) group._supplierKeys.push(nameKey);
    identityKeys.forEach(key => {
      if (!group._supplierIdentityKeys.includes(key)) group._supplierIdentityKeys.push(key);
      keyIndex.set(key, groupKey);
    });

    if (!group.name || String(supplier.name || '').length > String(group.name || '').length) group.name = supplier.name;
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
  });

  return Array.from(groups.values()).sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'ru'));
};
