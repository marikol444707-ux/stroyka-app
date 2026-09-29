export function supplierPublicRequisites(values = {}) {
  const fields = ['inn', 'kpp', 'ogrn', 'actualAddress', 'bank', 'bik', 'account',
    'korAccount', 'directorName', 'directorPosition', 'website', 'phone', 'email', 'specialization'];
  return { ...Object.fromEntries(fields.filter(key => key in values).map(key => [key, values[key]])),
    ...(values.companyName ? { name: values.companyName } : {}),
    legalAddress: values.address || values.legalAddress || '',
  };
}
