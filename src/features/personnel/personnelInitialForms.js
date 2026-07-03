export const createStaffDocumentForm = (overrides = {}) => ({
  docType: 'другое',
  title: '',
  fileUrl: '',
  signedAt: '',
  expiresAt: '',
  notes: '',
  ...overrides,
});

export const createUserForm = (overrides = {}) => ({
  name: '',
  email: '',
  password: '',
  role: 'прораб',
  projectId: '',
  projectName: '',
  assignedProjects: [],
  assignedPackages: [],
  active: true,
  ...overrides,
});

export const createPieceworkForm = (overrides = {}) => ({
  staffId: '',
  description: '',
  unit: 'м2',
  quantity: '',
  pricePerUnit: '',
  project: '',
  ...overrides,
});

export const createContractForm = (overrides = {}) => ({
  masterId: '',
  masterName: '',
  contractType: 'ГПХ',
  contractNumber: '',
  project: '',
  startDate: '',
  endDate: '',
  ...overrides,
});

export const createInterimActForm = (overrides = {}) => ({
  masterId: '',
  masterName: '',
  project: '',
  workPackage: '',
  periodStart: '',
  periodEnd: '',
  ...overrides,
});

export const createBrigadeContractForm = (overrides = {}) => ({
  projectId: '',
  projectName: '',
  brigadeName: '',
  contractorType: 'Своя бригада',
  contractorId: '',
  notes: '',
  pricelistId: '',
  ...overrides,
});

export const createBrigadeItemForm = (overrides = {}) => ({
  name: '',
  unit: 'м',
  quantity: '',
  priceSmeta: '',
  priceBrigade: '',
  estimateSection: '',
  workPackage: 'Основная',
  estimateItemKey: '',
  ...overrides,
});
