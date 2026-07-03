export const createProjectForm = (overrides = {}) => ({
  name: '',
  client: '',
  status: 'Планирование',
  budget: '',
  deadline: '',
  progress: 0,
  tasks: [],
  pricelistId: null,
  ...overrides,
});

export const createClientForm = (overrides = {}) => ({
  name: '',
  phone: '',
  email: '',
  status: 'Активный',
  notes: '',
  ...overrides,
});
