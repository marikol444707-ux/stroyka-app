export const createLeadForm = (overrides = {}) => ({
  name: '',
  phone: '',
  email: '',
  source: '',
  budget: '',
  notes: '',
  stage: 'Новый',
  photoUrl: '',
  contractSubject: '',
  ...overrides,
});
