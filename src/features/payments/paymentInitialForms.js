export const createActPaymentForm = () => ({
  amount: '',
  paymentType: 'Наличный расчёт',
  paidBy: '',
  date: '',
  notes: '',
});

export const createBrigadePaymentForm = () => ({
  amount: '',
  paidBy: '',
  paidDate: '',
  note: '',
});

export const createAccountablePaymentForm = (overrides = {}) => ({
  givenTo: '',
  amount: '',
  paymentMethod: 'Наличные',
  purpose: '',
  date: '',
  projectName: '',
  ...overrides,
});

export const createAccountableExpenseForm = (overrides = {}) => ({
  description: '',
  amount: '',
  photoUrl: '',
  ...overrides,
});

export const createManualExpenseForm = (overrides = {}) => ({
  category: 'materials',
  customCategory: '',
  projectName: '',
  amount: '',
  note: '',
  date: '',
  photoUrl: '',
  ...overrides,
});

export const createOwnExpenseForm = (overrides = {}) => ({
  projectName: '',
  category: 'other',
  description: '',
  amount: '',
  photoUrl: '',
  date: '',
  ...overrides,
});

export const createExpenseReportForm = (overrides = {}) => ({
  reportType: 'Авансовый отчёт',
  employeeName: '',
  projectName: '',
  purpose: '',
  issuedAmount: '',
  spentAmount: '',
  balance: '',
  dateFrom: '',
  dateTo: '',
  ...overrides,
});
