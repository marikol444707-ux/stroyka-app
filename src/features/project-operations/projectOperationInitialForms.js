export const createRoomForm = (overrides = {}) => ({
  project: '',
  name: '',
  floor: '',
  liter: '',
  roomType: 'Комната',
  floorArea: '',
  wallArea: '',
  ceilingArea: '',
  height: '',
  ceilingType: 'Простой',
  wallMaterial: 'Штукатурка',
  floorMaterial: 'Стяжка',
  photoUrl: '',
  notes: '',
  ...overrides,
});

export const createWindowForm = (overrides = {}) => ({
  roomId: '',
  name: 'Окно 1',
  width: '',
  height: '',
  windowType: 'ПВХ',
  revealDepth: '',
  revealMaterial: 'Штукатурка',
  ...overrides,
});

export const createDoorForm = (overrides = {}) => ({
  roomId: '',
  name: 'Дверь 1',
  width: '',
  height: '',
  doorType: 'Деревянная',
  doorPurpose: 'Межкомнатная',
  revealDepth: '',
  revealMaterial: 'Штукатурка',
  ...overrides,
});

export const createWeatherForm = () => ({
  projectName: '',
  date: '',
  temperature: '',
  condition: 'Ясно',
  windSpeed: '',
  notes: '',
});

export const createChecklistForm = (overrides = {}) => ({
  name: '',
  template: '',
  ...overrides,
});

export const createPrescriptionForm = (overrides = {}) => ({
  number: '',
  violation: '',
  deadline: '',
  responsible: '',
  photoUrl: '',
  ...overrides,
});

export const createInspectionOrderForm = (overrides = {}) => ({
  body: 'ГСН',
  inspector: '',
  description: '',
  recommendations: '',
  date: '',
  deadline: '',
  ...overrides,
});

export const createWarrantyDefectForm = (overrides = {}) => ({
  description: '',
  foundAt: new Date().toISOString().split('T')[0],
  reportedBy: '',
  reporterPhone: '',
  severity: 'Средний',
  ...overrides,
});

export const createTbEntryForm = (overrides = {}) => ({
  project: '',
  type: 'Вводный инструктаж',
  participants: [],
  date: '',
  program: '',
  instructionText: '',
  aiLoading: false,
  ...overrides,
});

export const createProjectStageForm = (overrides = {}) => ({
  name: '',
  status: 'Не начат',
  startDate: '',
  endDate: '',
  progress: 0,
  responsible: '',
  notes: '',
  ...overrides,
});
