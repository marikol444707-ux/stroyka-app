import { useEffect } from 'react';

export function useSupplierRequisitesSync({
  setSupplierRequisites,
  suppliers,
  user,
}) {
  useEffect(() => {
    if (!user || user.role !== 'поставщик' || !suppliers?.length) return;
    const my = suppliers.find(s => s.name === user.name || s.email === user.email || s.user_id === user.id);
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
