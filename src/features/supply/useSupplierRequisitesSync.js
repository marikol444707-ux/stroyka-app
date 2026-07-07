import { useEffect } from 'react';
import { groupSuppliers, supplierIdentityKeys } from '../../utils/supplierUtils';

const normalizeSupplierIdentity = value => String(value || '')
  .toLowerCase()
  .replace(/["'«»„“”]/g, '')
  .replace(/\b(ооо|оао|ао|ип|зао|пао|общество|с ограниченной|ответственностью)\b/g, ' ')
  .replace(/[^а-яa-z0-9]+/gi, ' ')
  .replace(/\s+/g, ' ')
  .trim();

export function useSupplierRequisitesSync({
  setSupplierRequisites,
  suppliers,
  user,
}) {
  useEffect(() => {
    if (!user || user.role !== 'поставщик' || !suppliers?.length) return;
    const currentUserId = user?.id || user?.userId || user?.user_id || '';
    const currentUserEmail = String(user?.email || '').toLowerCase();
    const currentUserName = normalizeSupplierIdentity(user?.name);
    const currentUserKeys = supplierIdentityKeys({
      name: user?.name || '',
      email: user?.email || '',
      phone: user?.phone || '',
    });
    const supplierGroups = groupSuppliers(suppliers || []);
    const my = supplierGroups.find(supplier => {
      const supplierUserId = supplier.userId || supplier.user_id || '';
      const supplierEmail = String(supplier.email || supplier.supplierEmail || supplier.supplier_email || '').toLowerCase();
      const identityKeys = supplier._supplierIdentityKeys || supplierIdentityKeys(supplier);
      return (supplierUserId && currentUserId && String(supplierUserId) === String(currentUserId))
        || (supplierEmail && currentUserEmail && supplierEmail === currentUserEmail)
        || (normalizeSupplierIdentity(supplier.name) && normalizeSupplierIdentity(supplier.name) === currentUserName)
        || currentUserKeys.some(key => identityKeys.includes(key));
    }) || (supplierGroups.length === 1 ? supplierGroups[0] : null);
    if (!my) return;
    setSupplierRequisites(prev => ({
      ...prev,
      companyName: my.name || prev.companyName || '',
      inn: my.inn || '',
      kpp: my.kpp || '',
      ogrn: my.ogrn || '',
      address: my.legal_address || my.legalAddress || prev.address || '',
      actualAddress: my.actual_address || my.actualAddress || '',
      bank: my.bank || '',
      bik: my.bik || '',
      account: my.account || '',
      korAccount: my.kor_account || my.korAccount || '',
      directorName: my.director_name || my.directorName || '',
      directorPosition: my.director_position || my.directorPosition || '',
      phone: my.phone || prev.phone || '',
      email: my.email || prev.email || '',
      website: my.website || '',
      specialization: my.specialization || '',
      category: my.category || '',
      contractUrl: my.contract_url || my.contractUrl || '',
      contractNumber: my.contract_number || my.contractNumber || '',
      contractDate: String(my.contract_date || my.contractDate || '').slice(0, 10),
      licenseUrl: my.license_url || my.licenseUrl || '',
      priceUrl: my.price_url || my.priceUrl || prev.priceUrl || '',
      notes: my.notes || prev.notes || '',
    }));
  }, [setSupplierRequisites, suppliers, user]);
}
