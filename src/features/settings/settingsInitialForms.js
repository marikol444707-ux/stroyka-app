export const createCompanyDocumentForm = (overrides = {}) => ({
  name: '',
  docType: 'Устав',
  fileUrl: '',
  expiresAt: '',
  ...overrides,
});

export const createCompanyRequisitesForm = (overrides = {}) => ({
  fullName: '',
  shortName: '',
  inn: '',
  kpp: '',
  ogrn: '',
  legalAddress: '',
  actualAddress: '',
  phone: '',
  email: '',
  directorName: '',
  directorPosition: 'Генеральный директор',
  basis: 'Устава',
  bankName: '',
  bik: '',
  rs: '',
  ks: '',
  ...overrides,
});

export const createProfileForm = (overrides = {}) => ({
  fullName: '',
  passport: '',
  inn: '',
  contractType: 'ГПХ',
  bankAccount: '',
  bankName: '',
  phone: '',
  specialization: '',
  ogrnip: '',
  ...overrides,
});
